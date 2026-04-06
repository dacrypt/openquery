"""Honduras RTN source — SAR tax registry.

Queries Honduras' Servicio de Administración de Rentas (SAR) for
RTN (Registro Tributario Nacional) data.

Source: https://www.sar.gob.hn/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.hn.rtn import HnRtnResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

# Navigate directly to the iframe URL (the parent page embeds this)
SAR_URL = "https://enlacertn.sar.gob.hn/index.aspx"


@register
class HnRtnSource(BaseSource):
    """Query Honduran tax registry (SAR) by RTN."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="hn.rtn",
            display_name="SAR — Verificador RTN",
            description="Honduran tax registry: taxpayer name, status (Servicio de Administración de Rentas)",  # noqa: E501
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
            raise SourceError("hn.rtn", "RTN is required")
        return self._query(rtn.strip(), audit=input.audit)

    def _query(self, rtn: str, audit: bool = False) -> HnRtnResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("hn.rtn", "rtn", rtn)

        with browser.page(SAR_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill RTN — exact ID: #txtCriterio
                rtn_input = page.query_selector('#txtCriterio, input[name="txtCriterio"]')
                if not rtn_input:
                    raise SourceError("hn.rtn", "Could not find RTN input field")

                rtn_input.fill(rtn)
                logger.info("Filled RTN: %s", rtn)

                # Solve BotDetect CAPTCHA if present
                captcha_img = page.query_selector("#c_index_examplecaptcha_CaptchaImage")
                if captcha_img:
                    captcha_bytes = captcha_img.screenshot()
                    if captcha_bytes:
                        from openquery.core.captcha import OCRSolver

                        solver = OCRSolver(max_chars=6)
                        captcha_text = solver.solve(captcha_bytes)
                        captcha_input = page.query_selector("#CaptchaCodeTextBox")
                        if captcha_input:
                            captcha_input.fill(captcha_text)
                            logger.info("Solved CAPTCHA: %s", captcha_text)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit — exact ID: #btnBuscar
                submit = page.query_selector('#btnBuscar, input[name="btnBuscar"]')
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
                raise SourceError("hn.rtn", f"Query failed: {e}") from e

    def _parse_result(self, page, rtn: str) -> HnRtnResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = HnRtnResult(queried_at=datetime.now(), rtn=rtn)

        field_map = {
            "nombre": "nombre",
            "estado": "estado",
            "tipo": "tipo_contribuyente",
            "actividad": "actividad_economica",
            "direccion": "direccion",
            "departamento": "departamento",
            "municipio": "municipio",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    setattr(result, field, value)
                    break

        return result
