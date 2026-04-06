"""OSCE Impedidos source — Peruvian debarred contractors registry.

Queries the OSCE (Organismo Supervisor de las Contrataciones del Estado)
for debarred/impedidos contractors.

Flow:
1. Navigate to OSCE consultation page
2. Enter name or RUC
3. Parse result for debarment status

Source: https://www.osce.gob.pe/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.osce_impedidos import OsceImpedidosResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

OSCE_URL = "https://www.osce.gob.pe/consultasenlinea"


@register
class OsceImpedidosSource(BaseSource):
    """Query Peruvian debarred contractors registry (OSCE)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.osce_impedidos",
            display_name="OSCE — Impedidos de Contratar",
            description="Peruvian debarred/impedidos contractors registry (OSCE)",
            country="PE",
            url=OSCE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("ruc")
            or input.extra.get("company_name")
            or input.document_number
        )
        if not search_term:
            raise SourceError("pe.osce_impedidos", "ruc or company_name is required")
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> OsceImpedidosResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pe.osce_impedidos", "custom", search_term)

        with browser.page(OSCE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[type="text"], input[id*="ruc"], '
                    'input[id*="nombre"], input[id*="buscar"]'
                )
                if not search_input:
                    raise SourceError("pe.osce_impedidos", "Could not find search input field")

                search_input.fill(search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="buscar"], button[id*="consultar"]'
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
                raise SourceError("pe.osce_impedidos", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> OsceImpedidosResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        company_name = ""
        ruc = ""
        debarment_status = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue
            if ("nombre" in lower or "razon" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not company_name:
                    company_name = parts[1].strip()
            elif "ruc" in lower and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not ruc:
                    ruc = parts[1].strip()
            elif ("estado" in lower or "sancion" in lower or "impedimento" in lower) and ":" in stripped:  # noqa: E501
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not debarment_status:
                    debarment_status = parts[1].strip()

        is_debarred = any(
            phrase in body_lower
            for phrase in ["impedido", "inhabilitado", "sancionado", "suspendido"]
        )

        no_results = any(
            phrase in body_lower
            for phrase in ["no se encontr", "sin resultados", "no result"]
        )

        if no_results:
            is_debarred = False

        if not debarment_status:
            debarment_status = "Impedido" if is_debarred else "No encontrado"

        return OsceImpedidosResult(
            queried_at=datetime.now(),
            search_term=search_term,
            company_name=company_name,
            ruc=ruc,
            debarment_status=debarment_status,
            details={"is_debarred": is_debarred},
        )
