"""CNES source — Brazilian health facility registry.

Queries the CNES (Cadastro Nacional de Estabelecimentos de Saude)
for health facility data.

Flow:
1. Navigate to CNES consultation page
2. Enter CNES code or facility name
3. Parse result for facility data

Source: https://cnes.datasus.gov.br/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.cnes import CnesResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CNES_URL = "https://cnes.datasus.gov.br/pages/estabelecimentos/consulta.jsp"


@register
class CnesSource(BaseSource):
    """Query Brazilian health facility registry (CNES)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.cnes",
            display_name="CNES — Cadastro Nacional de Estabelecimentos de Saude",
            description="Brazilian health facility registry (CNES/DATASUS)",
            country="BR",
            url=CNES_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("cnes_code")
            or input.extra.get("facility_name")
            or input.document_number
        )
        if not search_term:
            raise SourceError("br.cnes", "cnes_code or facility_name is required")
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> CnesResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("br.cnes", "custom", search_term)

        with browser.page(CNES_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[type="text"], input[id*="cnes"], '
                    'input[id*="nome"], input[id*="buscar"]'
                )
                if not search_input:
                    raise SourceError("br.cnes", "Could not find search input field")

                search_input.fill(search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="buscar"], button[id*="pesquisar"]'
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
                raise SourceError("br.cnes", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> CnesResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        facility_name = ""
        cnes_code = ""
        facility_type = ""
        status = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue
            if ("nome" in lower or "estabelecimento" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not facility_name:
                    facility_name = parts[1].strip()
            elif "cnes" in lower and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not cnes_code:
                    cnes_code = parts[1].strip()
            elif ("tipo" in lower or "natureza" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not facility_type:
                    facility_type = parts[1].strip()
            elif "situacao" in lower and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not status:
                    status = parts[1].strip()

        found = any(
            phrase in body_lower
            for phrase in ["estabelecimento", "ativo", "habilitado", "cnes"]
        )

        if not status:
            status = "Ativo" if found else "Nao encontrado"

        return CnesResult(
            queried_at=datetime.now(),
            search_term=search_term,
            facility_name=facility_name,
            cnes_code=cnes_code,
            facility_type=facility_type,
            status=status,
            details={"found": found},
        )
