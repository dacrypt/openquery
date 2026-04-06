"""CMF Fiscalizados source — CMF supervised financial entities (Chile).

Queries the Chilean CMF portal for supervised/regulated financial entities.

Flow:
1. Navigate to the CMF fiscalizados search page
2. Enter institution name or RUT in the search field
3. Submit and parse the results table
4. Extract entity details: name, RUT, type, authorization status, address, branches
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.cmf_fiscalizados import CmfFiscalizadosResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CMF_FISCALIZADOS_URL = (
    "https://www.cmfchile.cl/portal/principal/613/w3-propertyvalue-43336.html"
)


@register
class CmfFiscalizadosSource(BaseSource):
    """Query CMF supervised financial entities by institution name or RUT."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.cmf_fiscalizados",
            display_name="CMF — Entidades Fiscalizadas",
            description="CMF supervised financial entities: RUT, authorization status, address",
            country="CL",
            url=CMF_FISCALIZADOS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("search_term", "") or input.document_number
        if not search_term:
            raise SourceError(
                "cl.cmf_fiscalizados",
                "Search term is required (pass via extra.search_term or document_number)",
            )
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> CmfFiscalizadosResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cl.cmf_fiscalizados", "search_term", search_term)

        with browser.page(CMF_FISCALIZADOS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill search input — CMF portal uses a text search field
                search_input = page.query_selector(
                    'input[name*="search"], input[name*="buscar"], '
                    'input[placeholder*="Entidad"], input[placeholder*="RUT"], '
                    'input[type="text"], input[type="search"]'
                )
                if not search_input:
                    raise SourceError(
                        "cl.cmf_fiscalizados", "Could not find search input field"
                    )
                search_input.fill(search_term)
                logger.info("Filled search_term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    "button:has-text('Buscar'), button:has-text('Consultar'), "
                    "button:has-text('Search')"
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(3000)
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
                raise SourceError("cl.cmf_fiscalizados", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> CmfFiscalizadosResult:
        body_text = page.inner_text("body")

        result = CmfFiscalizadosResult(search_term=search_term)

        # Parse entity name
        m = re.search(
            r"(?:raz[oó]n\s*social|nombre\s*(?:de\s*la\s*)?(?:entidad|empresa))[:\s]+([^\n]+)",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.entity_name = m.group(1).strip()

        # Parse RUT
        m = re.search(r"rut[:\s]+([0-9]{1,2}[.\d]*-[\dkK])", body_text, re.IGNORECASE)
        if m:
            result.rut = m.group(1).strip()

        # Parse entity type
        m = re.search(
            r"(?:tipo\s*(?:de\s*)?(?:entidad|instituci[oó]n)|categor[ií]a)[:\s]+([^\n]+)",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.entity_type = m.group(1).strip()

        # Parse authorization status
        m = re.search(
            r"(?:estado\s*(?:de\s*)?autorizaci[oó]n|autorizaci[oó]n|estado)[:\s]+([^\n]+)",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.authorization_status = m.group(1).strip()

        # Parse address
        m = re.search(
            r"(?:direcci[oó]n|domicilio)[:\s]+([^\n]+)",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.address = m.group(1).strip()

        # Parse table rows for structured details
        rows = page.query_selector_all("table tr, .resultado tr, .entity-details tr")
        details: dict[str, str] = {}
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                key = (cells[0].inner_text() or "").strip()
                val = (cells[1].inner_text() or "").strip()
                if key and val:
                    details[key] = val
                    # Map known keys to fields
                    key_lower = key.lower()
                    if "nombre" in key_lower or "raz" in key_lower:
                        result.entity_name = result.entity_name or val
                    elif "rut" in key_lower:
                        result.rut = result.rut or val
                    elif "tipo" in key_lower or "categor" in key_lower:
                        result.entity_type = result.entity_type or val
                    elif "autorizaci" in key_lower or "estado" in key_lower:
                        result.authorization_status = result.authorization_status or val
                    elif "direcci" in key_lower or "domicilio" in key_lower:
                        result.address = result.address or val

        result.details = details

        # Parse branches (sucursales) — may be listed as sub-rows or separate section
        branch_matches = re.findall(
            r"(?:sucursal|oficina|agencia)[:\s]+([^\n]+)",
            body_text,
            re.IGNORECASE,
        )
        result.branches = [b.strip() for b in branch_matches if b.strip()]

        return result
