"""Nicaragua INSS social security source.

Queries the INSS (Instituto Nicaragüense de Seguridad Social) portal
for affiliation status and contribution history.

Flow:
1. Navigate to https://www.inss.gob.ni/
2. Wait for search form to load
3. Fill cedula or INSS number
4. Submit and parse results
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ni.inss import NiInssResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

INSS_URL = "https://www.inss.gob.ni/"


@register
class NiInssSource(BaseSource):
    """Query Nicaragua INSS social security by cedula or INSS number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ni.inss",
            display_name="INSS — Afiliación Seguro Social Nicaragua",
            description=(
                "Nicaragua INSS social security: affiliation status, "
                "employer, and contribution history"
            ),
            country="NI",
            url=INSS_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query INSS for social security affiliation data."""
        cedula = input.extra.get("inss_number", "") or input.document_number
        if not cedula:
            raise SourceError("ni.inss", "cedula or inss_number is required")
        return self._query(cedula.strip(), audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> NiInssResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ni.inss", "cedula", cedula)

        with browser.page(INSS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                cedula_input = page.query_selector(
                    'input[id*="cedula"], input[name*="cedula"], '
                    'input[id*="inss"], input[name*="inss"], '
                    'input[id*="search"], input[name*="search"], '
                    'input[type="text"]'
                )
                if not cedula_input:
                    raise SourceError("ni.inss", "Could not find cedula input field")

                cedula_input.fill(cedula)
                logger.info("Filled cedula: %s", cedula)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    '#btnBuscar, input[name="btnBuscar"], '
                    '#btnConsultar, input[name="btnConsultar"], '
                    'button[type="submit"], input[type="submit"]'
                )
                if submit:
                    submit.click()
                else:
                    cedula_input.press("Enter")

                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cedula)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ni.inss", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> NiInssResult:
        """Parse INSS affiliation data from the page DOM."""
        body_text = page.inner_text("body")
        result = NiInssResult(cedula=cedula)
        details: dict[str, str] = {}

        field_map = {
            "afiliación": "affiliation_status",
            "afiliacion": "affiliation_status",
            "estado": "affiliation_status",
            "status": "affiliation_status",
            "empleador": "employer",
            "employer": "employer",
            "empresa": "employer",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            for label, attr in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, attr, value)
                    break
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val

        result.details = details
        logger.info(
            "INSS result — cedula=%s, affiliation_status=%s, employer=%s",
            result.cedula,
            result.affiliation_status,
            result.employer,
        )
        return result
