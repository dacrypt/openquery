"""MinCiencias/Colciencias research groups source — Colombia.

Queries ScienTI portal for research groups and researchers.

URL: https://scienti.minciencias.gov.co/
Input: researcher name (custom)
Returns: research group, category, details
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.colciencias import ColcienciasResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

COLCIENCIAS_URL = "https://scienti.minciencias.gov.co/ciencia-war/busquedaGrupoXNombre.do"


@register
class ColcienciasSource(BaseSource):
    """Query MinCiencias/Colciencias ScienTI portal for research groups."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.colciencias",
            display_name="MinCiencias — Grupos de Investigación (ScienTI)",
            description="Colombia MinCiencias ScienTI portal: research groups and researchers lookup",  # noqa: E501
            country="CO",
            url=COLCIENCIAS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "co.colciencias",
                "Provide a researcher/group name (extra.name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> ColcienciasResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying Colciencias/MinCiencias: search_term=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(COLCIENCIAS_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)  # noqa: E501
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[name*='nombre'], input[name*='busqueda'], input[type='text']"
                )
                if search_input:
                    search_input.fill(search_term)
                    submit = page.query_selector("input[type='submit'], button[type='submit']")
                    if submit:
                        submit.click()
                    else:
                        search_input.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                body_lower = body_text.lower()

                researcher_name = ""
                group = ""
                category = ""

                for line in body_text.split("\n"):
                    stripped = line.strip()
                    lower = stripped.lower()
                    if search_term.lower() in lower and not researcher_name:
                        researcher_name = stripped
                    if "grupo" in lower and not group:
                        group = stripped
                    if "categoría" in lower or "categoria" in lower or "category" in lower:
                        if ":" in stripped and not category:
                            category = stripped.split(":", 1)[1].strip()

                if not category:
                    for cat in ["A1", "A", "B", "C", "D"]:
                        if cat in body_text:
                            category = cat
                            break

                details = body_lower[:200] if body_lower else f"ScienTI query for: {search_term}"

            return ColcienciasResult(
                queried_at=datetime.now(),
                search_term=search_term,
                researcher_name=researcher_name,
                group=group,
                category=category,
                details=details,
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("co.colciencias", f"Query failed: {e}") from e
