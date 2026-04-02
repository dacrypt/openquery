"""JEP source — Colombian transitional justice processes.

Queries the JEP (Jurisdiccion Especial para la Paz) for transitional
justice case information by cedula or name.

Flow:
1. Navigate to JEP consultation page
2. Enter document number or name
3. Parse search results

Source: https://www.jep.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.jep import JepResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

JEP_URL = "https://www.jep.gov.co/"


@register
class JepSource(BaseSource):
    """Query Colombian transitional justice processes (JEP)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.jep",
            display_name="JEP \u2014 Jurisdicci\u00f3n Especial para la Paz",
            description="Colombian transitional justice processes (JEP)",
            country="CO",
            url=JEP_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in (DocumentType.CEDULA, DocumentType.CUSTOM):
            raise SourceError(
                "co.jep",
                f"Unsupported input type: {input.document_type}. Use cedula or CUSTOM.",
            )
        return self._query(input.document_number, audit=input.audit)

    def _query(self, query_value: str, audit: bool = False) -> JepResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.jep", "consulta", query_value)

        with browser.page(JEP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill search field with document or name
                search_input = page.query_selector(
                    'input[type="text"][id*="buscar"], '
                    'input[type="text"][id*="search"], '
                    'input[type="text"][id*="documento"], '
                    'input[type="text"][id*="nombre"], '
                    'input[type="search"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("co.jep", "Could not find search input field")

                search_input.fill(query_value)
                logger.info("Searching JEP for: %s", query_value)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'button[id*="search"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, query_value)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.jep", f"Query failed: {e}") from e

    def _parse_result(self, page, query_value: str) -> JepResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        # Check for no-results indicators
        no_results = any(phrase in body_lower for phrase in [
            "no se encontraron",
            "sin resultados",
            "no registra",
            "0 resultados",
        ])

        resultados: list[dict] = []

        if not no_results:
            # Try to extract result rows from tables or result containers
            rows = page.query_selector_all(
                "table tr, .resultado, .item-resultado, "
                ".search-result, .caso, .proceso"
            )

            for row in rows:
                text = row.inner_text()
                if not text.strip():
                    continue
                cells = text.split("\t")
                if len(cells) >= 2:
                    entry: dict[str, str] = {
                        "caso": cells[0].strip(),
                        "descripcion": cells[1].strip() if len(cells) > 1 else "",
                        "estado": cells[2].strip() if len(cells) > 2 else "",
                        "fecha": cells[3].strip() if len(cells) > 3 else "",
                    }
                    resultados.append(entry)
                elif text.strip():
                    resultados.append({"descripcion": text.strip()})

        tiene_procesos = len(resultados) > 0

        if tiene_procesos:
            mensaje = f"JEP {query_value}: {len(resultados)} proceso(s) encontrado(s)"
        else:
            mensaje = f"JEP {query_value}: No registra procesos"

        return JepResult(
            queried_at=datetime.now(),
            query=query_value,
            tiene_procesos=tiene_procesos,
            total_resultados=len(resultados),
            resultados=resultados,
            mensaje=mensaje,
        )
