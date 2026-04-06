"""Dominican Republic Superintendent of Banks source.

Queries the Superintendencia de Bancos for supervised financial entities.

URL: https://sb.gob.do/
Input: entity name (custom)
Returns: entity type, status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.do.superbanco import SuperbancoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUPERBANCO_URL = "https://sb.gob.do/supervision/entidades-supervisadas/"


@register
class SuperbancoSource(BaseSource):
    """Query Dominican Republic Superintendent of Banks for supervised entities."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="do.superbanco",
            display_name="Superintendencia de Bancos — Entidades Supervisadas (RD)",
            description="Dominican Republic Superintendent of Banks: supervised financial entity lookup",  # noqa: E501
            country="DO",
            url=SUPERBANCO_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("entity_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "do.superbanco",
                "Provide an entity name (extra.entity_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> SuperbancoResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying Superbanco RD: entity=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(SUPERBANCO_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)  # noqa: E501
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[type='search'], input[type='text'], input[placeholder*='entidad' i]"
                )
                if search_input:
                    search_input.fill(search_term)
                    submit = page.query_selector("button[type='submit'], input[type='submit']")
                    if submit:
                        submit.click()
                    else:
                        search_input.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                body_lower = body_text.lower()

                entity_name = ""
                entity_type = ""
                status = ""

                for line in body_text.split("\n"):
                    stripped = line.strip()
                    lower = stripped.lower()
                    if search_term.lower() in lower and not entity_name:
                        entity_name = stripped
                    if ("tipo" in lower or "categoría" in lower) and ":" in stripped and not entity_type:  # noqa: E501
                        entity_type = stripped.split(":", 1)[1].strip()

                if "supervisada" in body_lower or "activa" in body_lower:
                    status = "Supervisada"
                elif "no encontr" in body_lower:
                    status = "No encontrada"
                else:
                    status = "Consultada"

            return SuperbancoResult(
                queried_at=datetime.now(),
                search_term=search_term,
                entity_name=entity_name or search_term,
                entity_type=entity_type,
                status=status,
                details=f"Superbanco RD query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("do.superbanco", f"Query failed: {e}") from e
