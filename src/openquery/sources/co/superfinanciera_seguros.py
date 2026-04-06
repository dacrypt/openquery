"""Superfinanciera insurance companies source — Colombia.

Queries Superfinanciera for insurance entities by company name.

URL: https://www.superfinanciera.gov.co/
Input: company name (custom)
Returns: insurance entities
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.superfinanciera_seguros import SuperfinancieraSegurosResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUPERFINANCIERA_URL = (
    "https://www.superfinanciera.gov.co/jsp/loader.jsf"
    "?lServicio=PublicacionesPortal&lTipo=publicaciones&lFuncion=loadContenidoPublicacion"
    "&id=61884"
)


@register
class SuperfinancieraSegurosSource(BaseSource):
    """Query Superfinanciera insurance entities by company name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.superfinanciera_seguros",
            display_name="Superfinanciera — Entidades Aseguradoras",
            description="Colombia Superfinanciera insurance company lookup by name",
            country="CO",
            url=SUPERFINANCIERA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("company_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "co.superfinanciera_seguros",
                "Provide a company name (extra.company_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> SuperfinancieraSegurosResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying Superfinanciera seguros: search_term=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(
                    SUPERFINANCIERA_URL,
                    wait_until="domcontentloaded",
                    timeout=self._timeout * 1000,
                )
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                body_lower = body_text.lower()
                search_lower = search_term.lower()

                company_name = ""
                entity_type = ""
                status = ""

                found = search_lower in body_lower
                for line in body_text.split("\n"):
                    if search_lower in line.lower() and not company_name:
                        company_name = line.strip()

                if found:
                    if "asegurador" in body_lower:
                        entity_type = "Aseguradora"
                    elif "reasegurador" in body_lower:
                        entity_type = "Reaseguradora"
                    status = "Activa"
                else:
                    status = "No encontrada"

            return SuperfinancieraSegurosResult(
                queried_at=datetime.now(),
                search_term=search_term,
                company_name=company_name,
                entity_type=entity_type,
                status=status,
                details=f"Superfinanciera seguros query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("co.superfinanciera_seguros", f"Query failed: {e}") from e
