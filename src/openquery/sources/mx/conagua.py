"""CONAGUA water concessions source — Mexico.

Queries CONAGUA for water concession data.

URL: https://www.gob.mx/conagua
Input: concession name (custom)
Returns: holder, status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.conagua import ConaguaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CONAGUA_URL = "https://sigras.conagua.gob.mx/apps/sicorp/consulta_titulos.php"


@register
class ConaguaSource(BaseSource):
    """Query CONAGUA water concession data."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.conagua",
            display_name="CONAGUA — Concesiones de Agua",
            description="Mexico CONAGUA: water concession lookup by concession name or holder",
            country="MX",
            url=CONAGUA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("concession_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "mx.conagua",
                "Provide a concession name (extra.concession_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> ConaguaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying CONAGUA: concession=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(CONAGUA_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[type='search'], input[type='text'], input[name*='nombre']"
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

                concession_name = search_term
                holder = ""
                status = ""

                for line in body_text.split("\n"):
                    stripped = line.strip()
                    lower = stripped.lower()
                    if "titular" in lower and ":" in stripped and not holder:
                        holder = stripped.split(":", 1)[1].strip()
                    if ("vigencia" in lower or "estado" in lower) and ":" in stripped and not status:  # noqa: E501
                        status = stripped.split(":", 1)[1].strip()

                if not status:
                    if "vigente" in body_lower or "activa" in body_lower:
                        status = "Vigente"
                    elif "vencida" in body_lower or "cancelada" in body_lower:
                        status = "Vencida/Cancelada"
                    elif "no encontr" in body_lower:
                        status = "No encontrada"
                    else:
                        status = "Consultada"

            return ConaguaResult(
                queried_at=datetime.now(),
                search_term=search_term,
                concession_name=concession_name,
                holder=holder,
                status=status,
                details=f"CONAGUA query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("mx.conagua", f"Query failed: {e}") from e
