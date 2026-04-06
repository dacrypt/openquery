"""Supervigilancia private security companies source — Colombia.

Queries Supervigilancia registry for private security company license status.

URL: https://www.supervigilancia.gov.co/
Input: company name (custom)
Returns: license status, details
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.supervigilancia import SupervigilanciaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUPERVIGILANCIA_URL = "https://www.supervigilancia.gov.co/publicaciones/5751/consulta-de-empresas-de-vigilancia-y-seguridad-privada/"


@register
class SupervigilanciaSource(BaseSource):
    """Query Supervigilancia private security company registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.supervigilancia",
            display_name="Supervigilancia — Empresas de Vigilancia y Seguridad Privada",
            description="Colombia Supervigilancia: private security company license status lookup",
            country="CO",
            url=SUPERVIGILANCIA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("company_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "co.supervigilancia",
                "Provide a company name (extra.company_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> SupervigilanciaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying Supervigilancia: company=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(SUPERVIGILANCIA_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)  # noqa: E501
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[type='text'], input[name*='empresa'], input[placeholder*='empresa' i]"
                )
                if search_input:
                    search_input.fill(search_term)
                    submit = page.query_selector("input[type='submit'], button[type='submit'], button:has-text('Buscar')")  # noqa: E501
                    if submit:
                        submit.click()
                    else:
                        search_input.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                body_lower = body_text.lower()

                company_name = ""
                license_status = ""

                for line in body_text.split("\n"):
                    if search_term.lower() in line.lower() and not company_name:
                        company_name = line.strip()

                if "vigente" in body_lower or "activa" in body_lower:
                    license_status = "Vigente"
                elif "suspendida" in body_lower or "cancelada" in body_lower:
                    license_status = "Suspendida/Cancelada"
                elif "no encontr" in body_lower:
                    license_status = "No encontrada"
                else:
                    license_status = "Consultada"

            return SupervigilanciaResult(
                queried_at=datetime.now(),
                search_term=search_term,
                company_name=company_name or search_term,
                license_status=license_status,
                details=f"Supervigilancia query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("co.supervigilancia", f"Query failed: {e}") from e
