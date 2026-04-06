"""URSEA energy/water regulator source — Uruguay.

Queries URSEA for regulated energy and water entities.

URL: https://www.gub.uy/unidad-reguladora-servicios-energia-agua/
Input: entity name (custom)
Returns: regulation status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.uy.ursea import UrseaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

URSEA_URL = "https://www.gub.uy/unidad-reguladora-servicios-energia-agua/tramites-y-servicios/servicios/consulta-empresas-habilitadas"


@register
class UrseaSource(BaseSource):
    """Query URSEA regulated energy/water entities."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="uy.ursea",
            display_name="URSEA — Empresas Habilitadas (Uruguay)",
            description="Uruguay URSEA: regulated energy and water entity lookup",
            country="UY",
            url=URSEA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("entity_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "uy.ursea",
                "Provide an entity name (extra.entity_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> UrseaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying URSEA Uruguay: entity=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(URSEA_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[type='search'], input[type='text'], input[placeholder*='empresa' i]"
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
                regulation_status = ""

                for line in body_text.split("\n"):
                    if search_term.lower() in line.lower() and not entity_name:
                        entity_name = line.strip()

                if "habilitada" in body_lower or "autorizada" in body_lower:
                    regulation_status = "Habilitada"
                elif "no habilitada" in body_lower or "suspendida" in body_lower:
                    regulation_status = "No habilitada"
                elif "no encontr" in body_lower:
                    regulation_status = "No encontrada"
                else:
                    regulation_status = "Consultada"

            return UrseaResult(
                queried_at=datetime.now(),
                search_term=search_term,
                entity_name=entity_name or search_term,
                regulation_status=regulation_status,
                details=f"URSEA Uruguay query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("uy.ursea", f"Query failed: {e}") from e
