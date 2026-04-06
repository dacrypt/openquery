"""DT employer lookup source — Chile.

Queries Dirección del Trabajo for labor compliance by RUT.

URL: https://www.dt.gob.cl/
Input: RUT (custom)
Returns: labor compliance status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.dt import DtResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DT_URL = "https://www.dt.gob.cl/portal/1626/w3-propertyvalue-22978.html"


@register
class DtSource(BaseSource):
    """Query Dirección del Trabajo employer compliance by RUT."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.dt",
            display_name="DT — Dirección del Trabajo",
            description="Chile Dirección del Trabajo labor compliance lookup by RUT",
            country="CL",
            url=DT_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        rut = input.extra.get("rut", input.document_number).strip()
        if not rut:
            raise SourceError(
                "cl.dt",
                "Provide a RUT (extra.rut or document_number)",
            )
        return self._fetch(rut, audit=input.audit)

    def _fetch(self, rut: str, audit: bool = False) -> DtResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying DT Chile: rut=%s", rut)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(DT_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                rut_input = page.query_selector(
                    "input[name*='rut'], input[id*='rut'], input[placeholder*='rut' i], input[type='text']"  # noqa: E501
                )
                if rut_input:
                    rut_input.fill(rut)
                    submit = page.query_selector("button[type='submit'], input[type='submit']")
                    if submit:
                        submit.click()
                    else:
                        rut_input.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                body_lower = body_text.lower()

                employer_name = ""
                compliance_status = ""

                for line in body_text.split("\n"):
                    line_lower = line.lower()
                    if "razón social" in line_lower or "nombre" in line_lower:
                        parts = line.split(":")
                        if len(parts) > 1 and not employer_name:
                            employer_name = parts[1].strip()
                    if "estado" in line_lower or "cumplimiento" in line_lower:
                        parts = line.split(":")
                        if len(parts) > 1 and not compliance_status:
                            compliance_status = parts[1].strip()

                if not compliance_status:
                    if "al día" in body_lower or "vigente" in body_lower:
                        compliance_status = "Al día"
                    elif "deuda" in body_lower or "mora" in body_lower:
                        compliance_status = "Con deuda"

            return DtResult(
                queried_at=datetime.now(),
                rut=rut,
                employer_name=employer_name,
                compliance_status=compliance_status,
                details=f"DT Chile query for RUT: {rut}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("cl.dt", f"Query failed: {e}") from e
