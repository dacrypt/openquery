"""ANM mining registry source — Colombia.

Queries ANM for mining concessions by title number or company name.

URL: https://www.anm.gov.co/
Input: title number or search term (custom)
Returns: mining concession details
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.anm import AnmResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ANM_URL = "https://www.anm.gov.co/registro-minero/catastro-minero"


@register
class AnmSource(BaseSource):
    """Query ANM mining concession registry by title number or name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.anm",
            display_name="ANM — Catastro y Registro Minero",
            description="Colombia ANM mining concession registry lookup by title number",
            country="CO",
            url=ANM_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("title_number", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "co.anm",
                "Provide a title number (extra.title_number or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> AnmResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying ANM: search_term=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(ANM_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[name*='titulo'], input[id*='titulo'], "
                    "input[placeholder*='título' i], input[type='text']"
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

                title_number = ""
                holder = ""
                status = ""

                for line in body_text.split("\n"):
                    line_stripped = line.strip()
                    line_lower = line_stripped.lower()
                    if search_term.lower() in line_lower and not title_number:
                        title_number = line_stripped
                    if any(k in line_lower for k in ["titular", "beneficiario", "propietario"]):
                        parts = line_stripped.split(":")
                        if len(parts) > 1 and not holder:
                            holder = parts[1].strip()
                    if "estado" in line_lower:
                        parts = line_stripped.split(":")
                        if len(parts) > 1 and not status:
                            status = parts[1].strip()

                if not status:
                    if "vigente" in body_lower or "activo" in body_lower:
                        status = "Vigente"
                    elif "no encontr" in body_lower:
                        status = "No encontrado"

            return AnmResult(
                queried_at=datetime.now(),
                search_term=search_term,
                title_number=title_number or search_term,
                holder=holder,
                status=status,
                details=f"ANM query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("co.anm", f"Query failed: {e}") from e
