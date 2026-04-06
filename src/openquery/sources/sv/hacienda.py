"""El Salvador Hacienda DUI/NIT source.

Queries El Salvador's Ministerio de Hacienda / DGII portal for
DUI/NIT registration and taxpayer status confirmation.

Source: https://portaldgii.mh.gob.sv/ssc/serviciosinclave/consulta/duinit/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.sv.hacienda import SvHaciendaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

HACIENDA_URL = "https://portaldgii.mh.gob.sv/ssc/serviciosinclave/consulta/duinit/"


@register
class SvHaciendaSource(BaseSource):
    """Query El Salvador Hacienda (DGII) DUI/NIT registration status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="sv.hacienda",
            display_name="Hacienda / DGII — Consulta DUI/NIT",
            description="El Salvador Hacienda DUI/NIT registration and taxpayer status (DGII)",
            country="SV",
            url=HACIENDA_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        dui = input.extra.get("dui", "") or input.document_number
        if not dui:
            raise SourceError("sv.hacienda", "DUI is required")
        return self._query(dui.strip(), audit=input.audit)

    def _query(self, dui: str, audit: bool = False) -> SvHaciendaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("sv.hacienda", "dui", dui)

        with browser.page(HACIENDA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill DUI input
                dui_input = page.query_selector(
                    'input[id*="dui"], input[name*="dui"], '
                    'input[id*="DUI"], input[name*="DUI"], '
                    'input[type="text"]'
                )
                if not dui_input:
                    raise SourceError("sv.hacienda", "Could not find DUI input field")

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

                # Submit
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
                raise SourceError("sv.hacienda", f"Query failed: {e}") from e

    def _parse_result(self, page, dui: str) -> SvHaciendaResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SvHaciendaResult(queried_at=datetime.now(), dui=dui)
        details: dict[str, str] = {}

        field_map = {
            "nit": "nit",
            "estado": "taxpayer_status",
            "situación": "taxpayer_status",
            "situacion": "taxpayer_status",
            "condición": "taxpayer_status",
            "condicion": "taxpayer_status",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            for label, attr in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, attr, value)
                    break
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val

        result.details = details
        return result
