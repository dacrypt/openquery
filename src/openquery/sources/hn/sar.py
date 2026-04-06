"""Honduras SAR tax/RTN source.

Queries Honduras' Servicio de Administración de Rentas (SAR) for
RTN (Registro Tributario Nacional) taxpayer data.

Source: https://www.sar.gob.hn/registro-tributario-nacional-rtn/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.hn.sar import HnSarResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SAR_URL = "https://www.sar.gob.hn/registro-tributario-nacional-rtn/"


@register
class HnSarSource(BaseSource):
    """Query Honduras SAR tax registry by RTN number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="hn.sar",
            display_name="SAR — Registro Tributario Nacional",
            description="Honduras SAR tax registry: taxpayer name, address, status by RTN",
            country="HN",
            url=SAR_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        rtn = input.extra.get("rtn", "") or input.document_number
        if not rtn:
            raise SourceError("hn.sar", "RTN is required")
        return self._query(rtn.strip(), audit=input.audit)

    def _query(self, rtn: str, audit: bool = False) -> HnSarResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("hn.sar", "rtn", rtn)

        with browser.page(SAR_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill RTN input
                rtn_input = page.query_selector(
                    'input[id*="rtn"], input[name*="rtn"], '
                    'input[id*="RTN"], input[name*="RTN"], '
                    'input[id*="numero"], input[name*="numero"], '
                    'input[type="text"]'
                )
                if not rtn_input:
                    raise SourceError("hn.sar", "Could not find RTN input field")

                rtn_input.fill(rtn)
                logger.info("Filled RTN: %s", rtn)

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
                    rtn_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, rtn)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("hn.sar", f"Query failed: {e}") from e

    def _parse_result(self, page, rtn: str) -> HnSarResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = HnSarResult(queried_at=datetime.now(), rtn=rtn)
        details: dict[str, str] = {}

        field_map = {
            "nombre": "taxpayer_name",
            "razón social": "taxpayer_name",
            "razon social": "taxpayer_name",
            "dirección": "address",
            "direccion": "address",
            "fecha": "registration_date",
            "estado": "tax_status",
            "situación": "tax_status",
            "situacion": "tax_status",
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
