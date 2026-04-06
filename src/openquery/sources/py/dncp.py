"""Paraguay DNCP government procurement source.

Queries DNCP (Dirección Nacional de Contrataciones Públicas) for
supplier contract data by supplier name.

URL: https://www.contrataciones.gov.py/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.py.dncp import PyDncpContract, PyDncpResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DNCP_URL = "https://www.contrataciones.gov.py/"
DNCP_API_URL = "https://www.contrataciones.gov.py/buscador/licitaciones.html"


@register
class PyDncpSource(BaseSource):
    """Query Paraguay DNCP government procurement portal."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="py.dncp",
            display_name="DNCP — Contrataciones Públicas Paraguay",
            description=(
                "Paraguay DNCP government procurement portal: supplier contracts, "
                "amounts, and procurement status by supplier name"
            ),
            country="PY",
            url=DNCP_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query DNCP for supplier contract data."""
        search_term = input.extra.get("supplier_name", "") or input.document_number
        if not search_term:
            raise SourceError("py.dncp", "supplier_name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> PyDncpResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("py.dncp", "supplier_name", search_term)

        with browser.page(DNCP_API_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="proveedor"], input[name*="proveedor"], '
                    'input[id*="search"], input[name*="search"], '
                    'input[id*="buscar"], input[name*="buscar"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("py.dncp", "Could not find search input field")

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
                    search_input.press("Enter")

                page.wait_for_timeout(4000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("py.dncp", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> PyDncpResult:
        """Parse procurement contract data from the page DOM."""
        body_text = page.inner_text("body")
        result = PyDncpResult(search_term=search_term)
        details: dict[str, str] = {}
        contracts: list[PyDncpContract] = []

        rows = page.query_selector_all("table tr")
        for row in rows[1:]:
            cells = row.query_selector_all("td")
            if not cells:
                continue
            values = [(c.inner_text() or "").strip() for c in cells]
            if len(values) >= 1:
                contract = PyDncpContract(
                    convocatoria=values[0] if len(values) > 0 else "",
                    monto=values[1] if len(values) > 1 else "",
                    estado=values[2] if len(values) > 2 else "",
                    fecha=values[3] if len(values) > 3 else "",
                )
                contracts.append(contract)

        result.contracts = contracts
        result.total_contracts = len(contracts)

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val

        result.details = details
        logger.info(
            "DNCP result — search=%s, contracts=%d", search_term, result.total_contracts
        )
        return result
