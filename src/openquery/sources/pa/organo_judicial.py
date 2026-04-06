"""Panama Organo Judicial source — court case search.

Queries Panama's Organo Judicial portal for court case information.
Browser-based, public access (limited fields without access key).

Portal: https://ojpanama.organojudicial.gob.pa/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pa.organo_judicial import OrganoJudicialResult, PaProcesoRecord
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

PORTAL_URL = "https://ojpanama.organojudicial.gob.pa/"


@register
class OrganoJudicialSource(BaseSource):
    """Query Panama Organo Judicial for court case information."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pa.organo_judicial",
            display_name="Organo Judicial — Consulta de Procesos",
            description=(
                "Panama court case search via Organo Judicial portal "
                "(ojpanama.organojudicial.gob.pa)"
            ),
            country="PA",
            url=PORTAL_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_value = input.extra.get("case_number", "") or input.document_number.strip()
        if not search_value:
            raise SourceError("pa.organo_judicial", "Case number or cedula is required")
        return self._query(search_value, audit=input.audit)

    def _query(self, search_value: str, audit: bool = False) -> OrganoJudicialResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("pa.organo_judicial", "search", search_value)

        with browser.page(PORTAL_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                # Find search input
                search_input = page.query_selector(
                    'input[type="text"][id*="cedula"], '
                    'input[type="text"][name*="cedula"], '
                    'input[type="text"][id*="proceso"], '
                    'input[type="text"][name*="proceso"], '
                    'input[type="text"][placeholder*="edula"], '
                    'input[type="text"][placeholder*="roceso"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("pa.organo_judicial", "Could not find search input field")

                search_input.fill(search_value)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit form
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'button[class*="btn-primary"], button'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    search_input.press("Enter")

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_value)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pa.organo_judicial", f"Query failed: {e}") from e

    def _parse_result(self, page: object, search_value: str) -> OrganoJudicialResult:
        from datetime import datetime

        body_text = page.inner_text("body")  # type: ignore[union-attr]
        body_lower = body_text.lower()

        processes: list[PaProcesoRecord] = []

        if any(phrase in body_lower for phrase in ("no se encontr", "no registra", "sin result")):
            return OrganoJudicialResult(
                queried_at=datetime.now(),
                search_value=search_value,
                total=0,
                processes=[],
            )

        # Try to parse table rows for process records
        try:
            rows = page.query_selector_all("table tr")  # type: ignore[union-attr]
            for row in rows[1:]:  # skip header row
                cells = row.query_selector_all("td")
                cell_texts = [c.inner_text().strip() for c in cells]
                if len(cell_texts) >= 2 and cell_texts[0]:
                    processes.append(PaProcesoRecord(
                        case_number=cell_texts[0] if len(cell_texts) > 0 else "",
                        court=cell_texts[1] if len(cell_texts) > 1 else "",
                        case_type=cell_texts[2] if len(cell_texts) > 2 else "",
                        status=cell_texts[3] if len(cell_texts) > 3 else "",
                        filing_date=cell_texts[4] if len(cell_texts) > 4 else "",
                        parties=cell_texts[5] if len(cell_texts) > 5 else "",
                    ))
        except Exception:
            # Fall back to text parsing if table extraction fails
            for line in body_text.split("\n"):
                stripped = line.strip()
                keywords = ("proceso", "expediente", "juzgado")
                if stripped and any(kw in stripped.lower() for kw in keywords):
                    processes.append(PaProcesoRecord(case_number=stripped))

        return OrganoJudicialResult(
            queried_at=datetime.now(),
            search_value=search_value,
            total=len(processes),
            processes=processes,
        )
