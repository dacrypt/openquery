"""ISP source — Chilean health product registry.

Queries the ISP (Instituto de Salud Publica) for sanitary registrations.

Flow:
1. Navigate to ISP consultation page
2. Enter product name
3. Parse result for registration number, status

Source: https://www.ispch.cl/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.isp import IspResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ISP_URL = "https://www.ispch.cl/anamed/subdeptoMedic/listadoMedicamentos.asp"


@register
class IspSource(BaseSource):
    """Query Chilean health product registry (ISP)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.isp",
            display_name="ISP — Registro de Productos Sanitarios",
            description="Chilean health product sanitary registration registry (ISP)",
            country="CL",
            url=ISP_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("product_name") or input.document_number
        if not search_term:
            raise SourceError("cl.isp", "product_name is required")
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> IspResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cl.isp", "custom", search_term)

        with browser.page(ISP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[type="text"], input[name*="nombre"], '
                    'input[id*="nombre"], input[id*="buscar"]'
                )
                if not search_input:
                    raise SourceError("cl.isp", "Could not find search input field")

                search_input.fill(search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'input[type="button"][value*="uscar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("cl.isp", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> IspResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        product_name = ""
        registration_number = ""
        status = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue
            if ("nombre" in lower or "producto" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not product_name:
                    product_name = parts[1].strip()
            elif ("n°" in lower or "numero" in lower or "registro" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not registration_number:
                    registration_number = parts[1].strip()
            elif "estado" in lower and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not status:
                    status = parts[1].strip()

        found = any(
            phrase in body_lower
            for phrase in ["registro sanitario", "inscrit", "autorizado", "vigente"]
        )

        if not status:
            status = "Encontrado" if found else "No encontrado"

        return IspResult(
            queried_at=datetime.now(),
            search_term=search_term,
            product_name=product_name,
            registration_number=registration_number,
            status=status,
            details={"found": found},
        )
