"""OSIPTEL source — Peru telecom operators registry.

Queries Peru's OSIPTEL for telecom operator and service data.

Flow:
1. Navigate to the OSIPTEL consultation page
2. Enter operator name or phone number
3. Submit and parse result

Source: https://www.osiptel.gob.pe/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.osiptel import OsiptelResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

OSIPTEL_URL = "https://www.osiptel.gob.pe/"


@register
class OsiptelSource(BaseSource):
    """Query Peru's OSIPTEL telecom operators registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.osiptel",
            display_name="OSIPTEL — Organismo Supervisor de Telecomunicaciones",
            description="Peru telecom operators: operator data, service type, and coverage",
            country="PE",
            url=OSIPTEL_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("pe.osiptel", f"Unsupported input type: {input.document_type}")

        operator = input.extra.get("operator", "").strip()
        phone = input.extra.get("phone", "").strip()

        if not operator and not phone:
            raise SourceError("pe.osiptel", "Must provide extra['operator'] or extra['phone']")

        return self._query(search_term=operator or phone, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> OsiptelResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("pe.osiptel", "operador", search_term)

        with browser.page(OSIPTEL_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="buscar"], input[name*="buscar"], '
                    'input[id*="operador"], input[name*="operador"], '
                    'input[id*="telefono"], input[name*="telefono"], '
                    'input[placeholder*="operador" i], input[type="text"]'
                )
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar")'
                )
                if submit:
                    submit.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(4000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pe.osiptel", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> OsiptelResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = OsiptelResult(queried_at=datetime.now(), search_term=search_term)
        details: dict = {}

        rows = page.query_selector_all("table tr, .result tr")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip()
                value = (cells[1].inner_text() or "").strip()
                if label and value:
                    details[label] = value
                    label_lower = label.lower()
                    if "operador" in label_lower or "empresa" in label_lower:
                        result.operator_name = value
                    elif "servicio" in label_lower or "tipo" in label_lower:
                        result.service_type = value

        if details:
            result.details = details

        # Fallback: body text scan
        if not result.operator_name:
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if ("operador" in lower or "empresa" in lower) and ":" in stripped:
                    result.operator_name = stripped.split(":", 1)[1].strip()
                elif ("servicio" in lower or "tipo" in lower) and ":" in stripped and not result.service_type:
                    result.service_type = stripped.split(":", 1)[1].strip()

        return result
