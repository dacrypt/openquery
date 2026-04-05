"""DNRPA source — Argentine vehicle registry (Direccion Nacional de Registros de la Propiedad del Automotor).

Queries DNRPA for vehicle registration info by plate (dominio).
The portal likely uses a CAPTCHA.

Flow:
1. Navigate to DNRPA portal
2. Enter dominio (plate)
3. Solve CAPTCHA if present
4. Submit and parse vehicle info
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.dnrpa import DnrpaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DNRPA_URL = "https://www.dnrpa.gov.ar/portal_dnrpa/radicacion2.php"


@register
class DnrpaSource(BaseSource):
    """Query Argentine vehicle registry (DNRPA) by plate (dominio)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.dnrpa",
            display_name="DNRPA — Registro Automotor",
            description="Argentine vehicle registry: registration details by plate (dominio)",
            country="AR",
            url=DNRPA_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError("ar.dnrpa", f"Unsupported document type: {input.document_type}")
        return self._query(input.document_number, audit=input.audit)

    def _query(self, dominio: str, audit: bool = False) -> DnrpaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("ar.dnrpa", "placa", dominio)

        with browser.page(DNRPA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # The radicacion2.php page has a table with two textboxes:
                # 1st textbox = Dominio (plate), 2nd textbox = Código verificador (CAPTCHA)
                all_inputs = page.query_selector_all('input[type="text"], input:not([type])')
                if not all_inputs:
                    raise SourceError("ar.dnrpa", "Could not find input fields on radicacion page")

                # First input is the dominio field
                plate_input = all_inputs[0]
                plate_input.fill(dominio.upper())
                logger.info("Filled dominio: %s", dominio)

                # Solve CAPTCHA if present — second textbox is the captcha code field
                captcha_input = all_inputs[1] if len(all_inputs) > 1 else None
                if captcha_input:
                    # The CAPTCHA image is in the same table — find it and solve via LLM/OCR
                    captcha_img = page.query_selector('img[alt*="verificador" i], img[alt*="captcha" i], table img')
                    if captcha_img:
                        from openquery.core.captcha import (
                            ChainedSolver,
                            LLMCaptchaSolver,
                            OCRSolver,
                        )
                        solvers = []
                        try:
                            solvers.append(LLMCaptchaSolver())
                        except Exception:
                            pass
                        solvers.append(OCRSolver(max_chars=6))
                        chain = ChainedSolver(solvers)
                        for attempt in range(1, 4):
                            try:
                                image_bytes = captcha_img.screenshot()
                                if image_bytes and len(image_bytes) >= 100:
                                    text = chain.solve(image_bytes)
                                    if text:
                                        captcha_input.fill(text)
                                        logger.info("CAPTCHA solved (attempt %d): %s", attempt, text)
                                        break
                            except Exception as e:
                                logger.warning("CAPTCHA attempt %d failed: %s", attempt, e)
                            # Refresh CAPTCHA
                            refresh = page.query_selector('a[href*="history.go"], a:has-text("Cargar nuevo")')
                            if refresh:
                                refresh.click()
                                page.wait_for_timeout(1000)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit via "Consultar" button
                submit = page.query_selector(
                    'button:has-text("Consultar"), input[value*="Consultar" i], '
                    'button[type="submit"], input[type="submit"]'
                )
                if submit:
                    submit.click()
                else:
                    plate_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, dominio)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ar.dnrpa", f"Query failed: {e}") from e

    def _parse_result(self, page, dominio: str) -> DnrpaResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = DnrpaResult(queried_at=datetime.now(), dominio=dominio.upper())

        # Parse fields
        field_patterns = [
            (r"(?:registro\s*seccional)[:\s]+([^\n]+)", "registro_seccional"),
            (r"(?:localidad)[:\s]+([^\n]+)", "localidad"),
            (r"(?:provincia)[:\s]+([^\n]+)", "provincia"),
            (r"(?:tipo\s*(?:de\s*)?veh[ií]culo)[:\s]+([^\n]+)", "tipo_vehiculo"),
        ]

        for pattern, field in field_patterns:
            m = re.search(pattern, body_text, re.IGNORECASE)
            if m:
                setattr(result, field, m.group(1).strip())

        # Try table-based parsing
        rows = page.query_selector_all("table tr, .resultado tr")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip().lower()
                value = (cells[1].inner_text() or "").strip()
                if "registro" in label and "seccional" in label:
                    result.registro_seccional = result.registro_seccional or value
                elif "localidad" in label:
                    result.localidad = result.localidad or value
                elif "provincia" in label:
                    result.provincia = result.provincia or value
                elif "tipo" in label and "vehiculo" in label:
                    result.tipo_vehiculo = result.tipo_vehiculo or value

        return result
