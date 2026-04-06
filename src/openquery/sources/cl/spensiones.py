"""Superintendencia de Pensiones source — Chilean AFP/AFC affiliation.

Queries the Chilean Superintendencia de Pensiones portal for AFP pension
affiliation and AFC unemployment insurance enrollment by RUT.
Browser-based, public, no login, no CAPTCHA.

URL: https://www.spensiones.cl/portal/institucional/597/w3-article-15721.html
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.spensiones import SpensionesResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SPENSIONES_URL = "https://www.spensiones.cl/portal/institucional/597/w3-article-15721.html"


@register
class SpensionesSource(BaseSource):
    """Query Chilean AFP/AFC affiliation via Superintendencia de Pensiones."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.spensiones",
            display_name="Superintendencia de Pensiones — Afiliación AFP/AFC",
            description=(
                "Chilean AFP pension affiliation and AFC unemployment insurance enrollment by RUT"
            ),
            country="CL",
            url=SPENSIONES_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        rut = input.extra.get("rut", "") or input.document_number
        if not rut:
            raise SourceError(
                "cl.spensiones", "RUT is required (pass via extra.rut or document_number)"
            )
        return self._query(rut, audit=input.audit)

    def _query(self, rut: str, audit: bool = False) -> SpensionesResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cl.spensiones", "rut", rut)

        with browser.page(SPENSIONES_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill RUT input
                rut_input = page.query_selector(
                    'input[name*="rut"], input[name*="RUT"], '
                    'input[id*="rut"], input[id*="RUT"], '
                    'input[placeholder*="RUT"], input[type="text"]'
                )
                if not rut_input:
                    raise SourceError("cl.spensiones", "Could not find RUT input field")
                rut_input.fill(rut)
                logger.info("Filled RUT: %s", rut)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    "button:has-text('Consultar'), button:has-text('Buscar')"
                )
                if submit:
                    submit.click()
                else:
                    rut_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, rut)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("cl.spensiones", f"Query failed: {e}") from e

    def _parse_result(self, page, rut: str) -> SpensionesResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = SpensionesResult(queried_at=datetime.now(), rut=rut)

        # Parse AFP name
        m = re.search(r"(?:AFP|afp|administradora)[:\s]+([^\n]+)", body_text, re.IGNORECASE)
        if m:
            result.afp_name = m.group(1).strip()

        # Parse AFP affiliation status — check "no afiliado" before "afiliado"
        m = re.search(
            r"(?:estado\s*(?:de\s*)?afiliaci[oó]n)[:\s]+([^\n]+)", body_text, re.IGNORECASE
        )
        if m:
            result.afp_status = m.group(1).strip()
        elif re.search(r"no\s+afiliado", body_text, re.IGNORECASE):
            result.afp_status = "NO AFILIADO"
        elif re.search(r"\bafiliado\b", body_text, re.IGNORECASE):
            result.afp_status = "AFILIADO"

        # Parse AFC status
        m = re.search(r"(?:AFC|seguro\s*de\s*cesant[ií]a)[:\s]+([^\n]+)", body_text, re.IGNORECASE)
        if m:
            result.afc_status = m.group(1).strip()
        elif re.search(r"afiliado.*AFC", body_text, re.IGNORECASE):
            result.afc_status = "AFILIADO"

        # Parse table data
        rows = page.query_selector_all("table tr, .resultado tr, .resultado-consulta tr")
        details: dict = {}
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip()
                value = (cells[1].inner_text() or "").strip()
                if label and value:
                    details[label] = value
                    label_lower = label.lower()
                    if "afp" in label_lower and not result.afp_name:
                        result.afp_name = value
                    elif (
                        "estado" in label_lower
                        and "afiliaci" in label_lower
                        and not result.afp_status
                    ):
                        result.afp_status = value
                    elif "afc" in label_lower and not result.afc_status:
                        result.afc_status = value

        if details:
            result.details = details

        return result
