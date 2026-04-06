"""ANT Agencia de Tierras land restitution source — Colombia.

Queries ANT for land restitution/formalization case status.

URL: https://www.agenciadetierras.gov.co/
Input: case number (custom)
Returns: case status, details
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.agencia_tierras import AgenciaTierrasResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

AGENCIA_TIERRAS_URL = "https://www.agenciadetierras.gov.co/atencion-al-ciudadano/consulta-de-casos/"


@register
class AgenciaTierrasSource(BaseSource):
    """Query ANT land restitution/formalization case status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.agencia_tierras",
            display_name="ANT — Agencia Nacional de Tierras",
            description="Colombia ANT land restitution/formalization case status lookup",
            country="CO",
            url=AGENCIA_TIERRAS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("case_number", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "co.agencia_tierras",
                "Provide a case number (extra.case_number or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> AgenciaTierrasResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying Agencia de Tierras: case=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(AGENCIA_TIERRAS_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)  # noqa: E501
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[type='text'], input[name*='caso'], input[name*='expediente']"
                )
                if search_input:
                    search_input.fill(search_term)
                    submit = page.query_selector("input[type='submit'], button[type='submit'], button:has-text('Consultar')")  # noqa: E501
                    if submit:
                        submit.click()
                    else:
                        search_input.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                body_lower = body_text.lower()

                case_status = ""
                if "activo" in body_lower or "vigente" in body_lower:
                    case_status = "Activo"
                elif "cerrado" in body_lower or "finalizado" in body_lower:
                    case_status = "Cerrado"
                elif "no encontr" in body_lower or "sin resultado" in body_lower:
                    case_status = "No encontrado"
                else:
                    case_status = "Consultado"

                details = f"ANT query for case: {search_term}"

            return AgenciaTierrasResult(
                queried_at=datetime.now(),
                search_term=search_term,
                case_status=case_status,
                details=details,
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("co.agencia_tierras", f"Query failed: {e}") from e
