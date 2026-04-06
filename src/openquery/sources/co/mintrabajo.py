"""MinTrabajo labor consultations source — Colombia.

Queries Ministerio del Trabajo for labor compliance by company NIT.

URL: https://www.mintrabajo.gov.co/
Input: company NIT (custom)
Returns: labor compliance status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.mintrabajo import MintrabajoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MINTRABAJO_URL = "https://www.mintrabajo.gov.co/web/guest/tramites-y-servicios/consultas"


@register
class MintrabajoSource(BaseSource):
    """Query MinTrabajo labor compliance by company NIT."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.mintrabajo",
            display_name="MinTrabajo — Consultas Laborales",
            description="Colombia Ministerio del Trabajo labor compliance lookup by company NIT",
            country="CO",
            url=MINTRABAJO_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        nit = input.extra.get("nit", input.document_number).strip()
        if not nit:
            raise SourceError(
                "co.mintrabajo",
                "Provide a company NIT (extra.nit or document_number)",
            )
        return self._fetch(nit, audit=input.audit)

    def _fetch(self, nit: str, audit: bool = False) -> MintrabajoResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying MinTrabajo: nit=%s", nit)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(MINTRABAJO_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)  # noqa: E501
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                nit_input = page.query_selector(
                    "input[name*='nit'], input[id*='nit'], input[placeholder*='nit' i], input[type='text']"  # noqa: E501
                )
                if nit_input:
                    nit_input.fill(nit)
                    submit = page.query_selector("button[type='submit'], input[type='submit']")
                    if submit:
                        submit.click()
                    else:
                        nit_input.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                body_lower = body_text.lower()

                company_name = ""
                compliance_status = ""

                for line in body_text.split("\n"):
                    line_lower = line.lower()
                    if "empresa" in line_lower or "razón social" in line_lower:
                        parts = line.split(":")
                        if len(parts) > 1 and not company_name:
                            company_name = parts[1].strip()
                    if "cumplimiento" in line_lower or "estado" in line_lower:
                        parts = line.split(":")
                        if len(parts) > 1 and not compliance_status:
                            compliance_status = parts[1].strip()

                if not compliance_status:
                    if "al día" in body_lower or "cumple" in body_lower:
                        compliance_status = "Al día"
                    elif "mora" in body_lower or "sancion" in body_lower:
                        compliance_status = "Incumplimiento"

            return MintrabajoResult(
                queried_at=datetime.now(),
                nit=nit,
                company_name=company_name,
                compliance_status=compliance_status,
                details=f"MinTrabajo query for NIT: {nit}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("co.mintrabajo", f"Query failed: {e}") from e
