"""El Salvador NIT/DUI source — DGII tax registry.

Queries El Salvador's Dirección General de Impuestos Internos (DGII)
for NIT/DUI homologation status. Public service, no login required.

Source: https://portaldgii.mh.gob.sv/ssc/serviciosinclave/consulta/duinit/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.sv.nit import SvNitResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DGII_URL = "https://portaldgii.mh.gob.sv/ssc/serviciosinclave/consulta/duinit/"


@register
class SvNitSource(BaseSource):
    """Query El Salvador DGII NIT/DUI homologation status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="sv.nit",
            display_name="DGII — Consulta DUI/NIT",
            description="El Salvador NIT/DUI homologation and taxpayer account status (DGII)",
            country="SV",
            url=DGII_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.CUSTOM],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        dui = input.extra.get("dui", "") or input.document_number
        if not dui:
            raise SourceError("sv.nit", "DUI is required (format: 00000000-0)")
        return self._query(dui.strip(), audit=input.audit)

    def _query(self, dui: str, audit: bool = False) -> SvNitResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("sv.nit", "dui", dui)

        with browser.page(DGII_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill DUI
                dui_input = page.query_selector(
                    '#txtDUI, input[name*="DUI"], input[name*="dui"], input[type="text"]'
                )
                if not dui_input:
                    raise SourceError("sv.nit", "Could not find DUI input field")

                dui_input.fill(dui)
                logger.info("Filled DUI: %s", dui)

                # Solve CAPTCHA if present
                captcha_img = page.query_selector(
                    'img[id*="captcha"], img[src*="captcha"], img[alt*="captcha"]'
                )
                if captcha_img:
                    captcha_bytes = captcha_img.screenshot()
                    if captcha_bytes:
                        from openquery.core.captcha import OCRSolver

                        solver = OCRSolver(max_chars=6)
                        captcha_text = solver.solve(captcha_bytes)
                        captcha_input = page.query_selector(
                            'input[id*="captcha"], input[name*="captcha"]'
                        )
                        if captcha_input:
                            captcha_input.fill(captcha_text)
                            logger.info("Solved CAPTCHA: %s", captcha_text)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Consultar"), button:has-text("Buscar")'
                )
                if submit:
                    submit.click()
                else:
                    dui_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, dui)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("sv.nit", f"Query failed: {e}") from e

    def _parse_result(self, page, dui: str) -> SvNitResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        lower = body_text.lower()

        result = SvNitResult(queried_at=datetime.now(), dui=dui)

        if "homologado" in lower:
            result.homologado = True
        if "activa" in lower:
            result.estado_cuenta = "Activa"
        elif "inactiva" in lower:
            result.estado_cuenta = "Inactiva"

        for line in body_text.split("\n"):
            stripped = line.strip()
            lo = stripped.lower()
            if "nit" in lo and ":" in stripped:
                result.nit = stripped.split(":", 1)[1].strip()
            elif "nombre" in lo and ":" in stripped:
                result.nombre = stripped.split(":", 1)[1].strip()

        return result
