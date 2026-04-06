"""MINEM mining concessions source — Peru.

Queries MINEM for mining concession rights by name.

URL: https://www.minem.gob.pe/
Input: concession name (custom)
Returns: mining rights
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.minem import MinemResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MINEM_URL = "https://geocatmin.ingemmet.gob.pe/geocatmin/"


@register
class MinemSource(BaseSource):
    """Query MINEM/INGEMMET mining concessions by name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.minem",
            display_name="MINEM — Concesiones Mineras (INGEMMET)",
            description="Peru MINEM mining concession rights lookup via INGEMMET GeoCatMin",
            country="PE",
            url=MINEM_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("concession_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "pe.minem",
                "Provide a concession name (extra.concession_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> MinemResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying MINEM concessions: search_term=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(MINEM_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[name*='concesion'], input[id*='concesion'], "
                    "input[placeholder*='concesión' i], input[type='text']"
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

                concession_name = ""
                holder = ""
                status = ""

                for line in body_text.split("\n"):
                    line_stripped = line.strip()
                    line_lower = line_stripped.lower()
                    if search_term.lower() in line_lower and not concession_name:
                        concession_name = line_stripped
                    if any(k in line_lower for k in ["titular", "propietario"]):
                        parts = line_stripped.split(":")
                        if len(parts) > 1 and not holder:
                            holder = parts[1].strip()
                    if "estado" in line_lower:
                        parts = line_stripped.split(":")
                        if len(parts) > 1 and not status:
                            status = parts[1].strip()

                if not status:
                    if "vigente" in body_lower:
                        status = "Vigente"
                    elif "no encontr" in body_lower:
                        status = "No encontrada"

            return MinemResult(
                queried_at=datetime.now(),
                search_term=search_term,
                concession_name=concession_name or search_term,
                holder=holder,
                status=status,
                details=f"MINEM concessions query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("pe.minem", f"Query failed: {e}") from e
