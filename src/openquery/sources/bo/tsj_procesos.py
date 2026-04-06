"""Bolivia TSJ source — court case search (Tribunal Supremo de Justicia).

Queries Bolivia's TSJ platform for court cases and rulings.

Source: https://tsj.bo/servicios-judiciales/plataforma-servicios/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.bo.tsj_procesos import TsjProcesosResult, TsjProcess
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

TSJ_URL = "https://tsj.bo/servicios-judiciales/plataforma-servicios/"


@register
class TsjProcesosSource(BaseSource):
    """Query Bolivia's TSJ court case platform by case number or party name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="bo.tsj_procesos",
            display_name="TSJ — Consulta de Procesos",
            description=(
                "Bolivia court cases: case status, rulings, parties (Tribunal Supremo de Justicia)"
            ),
            country="BO",
            url=TSJ_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_value = (
            input.extra.get("case_number", "")
            or input.extra.get("party_name", "")
            or input.document_number
        )
        if not search_value:
            raise SourceError("bo.tsj_procesos", "case_number or party_name is required")
        return self._query(search_value.strip(), audit=input.audit)

    def _query(self, search_value: str, audit: bool = False) -> TsjProcesosResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("bo.tsj_procesos", "search_value", search_value)

        with browser.page(TSJ_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[name*="proceso"], input[name*="expediente"], '
                    'input[id*="proceso"], input[placeholder*="proceso"], '
                    'input[placeholder*="expediente"], input[placeholder*="parte"], '
                    'input[type="search"], input[type="text"]'
                )
                if not search_input:
                    raise SourceError("bo.tsj_procesos", "Could not find search input field")

                search_input.fill(search_value)
                logger.info("Filled search value: %s", search_value)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar"), '
                    'button:has-text("Search")'
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_value)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("bo.tsj_procesos", f"Query failed: {e}") from e

    def _parse_result(self, page, search_value: str) -> TsjProcesosResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = TsjProcesosResult(queried_at=datetime.now(), search_value=search_value)

        processes: list[TsjProcess] = []

        # Try table rows first
        rows = page.query_selector_all("table tr")
        if rows:
            for row in rows[1:]:  # skip header
                cells = row.query_selector_all("td")
                if len(cells) >= 3:
                    texts = [c.inner_text().strip() for c in cells]
                    process = TsjProcess(
                        case_number=texts[0] if len(texts) > 0 else "",
                        court=texts[1] if len(texts) > 1 else "",
                        status=texts[2] if len(texts) > 2 else "",
                        parties=texts[3] if len(texts) > 3 else "",
                        date=texts[4] if len(texts) > 4 else "",
                    )
                    processes.append(process)

        # Fallback: parse text lines for labelled fields
        if not processes:
            current: dict[str, str] = {}
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if ("número" in lower or "expediente" in lower) and ":" in stripped:
                    if current:
                        processes.append(TsjProcess(**current))
                        current = {}
                    current["case_number"] = stripped.split(":", 1)[1].strip()
                elif "juzgado" in lower and ":" in stripped:
                    current["court"] = stripped.split(":", 1)[1].strip()
                elif "tribunal" in lower and ":" in stripped:
                    current["court"] = stripped.split(":", 1)[1].strip()
                elif "estado" in lower and ":" in stripped:
                    current["status"] = stripped.split(":", 1)[1].strip()
                elif "partes" in lower and ":" in stripped:
                    current["parties"] = stripped.split(":", 1)[1].strip()
                elif "fecha" in lower and ":" in stripped:
                    current["date"] = stripped.split(":", 1)[1].strip()
            if current:
                processes.append(TsjProcess(**current))

        result.processes = processes
        result.total = len(processes)
        return result
