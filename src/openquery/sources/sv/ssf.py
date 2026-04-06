"""SSF banking supervisor source — El Salvador.

Queries SSF (Superintendencia del Sistema Financiero) for supervised entities.

URL: https://www.ssf.gob.sv/
Input: entity name (custom)
Returns: entity type, status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.sv.ssf import SsfResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SSF_URL = "https://www.ssf.gob.sv/index.php/supervision/entidades-supervisadas"


@register
class SsfSource(BaseSource):
    """Query SSF El Salvador for supervised financial entities."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="sv.ssf",
            display_name="SSF — Superintendencia del Sistema Financiero (El Salvador)",
            description="El Salvador SSF: supervised financial entity lookup",
            country="SV",
            url=SSF_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("entity_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "sv.ssf",
                "Provide an entity name (extra.entity_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> SsfResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying SSF El Salvador: entity=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(SSF_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
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

                if "supervisada" in body_lower or "autorizada" in body_lower:
                    status = "Supervisada"
                elif "no encontr" in body_lower:
                    status = "No encontrada"
                else:
                    status = "Consultada"

            return SsfResult(
                queried_at=datetime.now(),
                search_term=search_term,
                entity_name=entity_name or search_term,
                entity_type=entity_type,
                status=status,
                details=f"SSF El Salvador query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("sv.ssf", f"Query failed: {e}") from e
