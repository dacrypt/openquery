"""SAT RFC source — Mexican RFC validator.

Queries the SAT portal to validate an RFC (Registro Federal de Contribuyentes)
and retrieve the taxpayer name and registration status.

Flow:
1. Navigate to SAT RFC validation page
2. Enter RFC (12-13 chars)
3. Solve image CAPTCHA
4. Submit and parse result
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.sat_rfc import SatRfcResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SAT_RFC_URL = "https://agsc.siat.sat.gob.mx/PTSC/ValidaRFC/index.jsf"


@register
class SatRfcSource(BaseSource):
    """Query Mexican SAT RFC validator for taxpayer name and registration status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.sat_rfc",
            display_name="SAT — Validación de RFC",
            description="Mexican SAT RFC validator: validity, taxpayer name, and status",
            country="MX",
            url=SAT_RFC_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=5,
        )

    def query(self, input: QueryInput) -> BaseModel:
        rfc = input.extra.get("rfc", "") or input.document_number
        if not rfc:
            raise SourceError("mx.sat_rfc", "RFC is required (pass via extra.rfc)")
        return self._query(rfc.upper().strip(), audit=input.audit)

    def _query(self, rfc: str, audit: bool = False) -> SatRfcResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("mx.sat_rfc", "rfc", rfc)

        with browser.page(SAT_RFC_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill RFC field
                rfc_input = page.query_selector(
                    'input[name*="rfc"], input[id*="rfc"], input[type="text"]'
                )
                if not rfc_input:
                    raise SourceError("mx.sat_rfc", "Could not find RFC input field")
                rfc_input.fill(rfc)
                logger.info("Filled RFC: %s", rfc)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    "button:has-text('Buscar'), button:has-text('Validar'), "
                    "button:has-text('Consultar')"
                )
                if submit:
                    submit.click()
                else:
                    rfc_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, rfc)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("mx.sat_rfc", f"Query failed: {e}") from e

    def _parse_result(self, page, rfc: str) -> SatRfcResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        result = SatRfcResult(queried_at=datetime.now(), rfc=rfc)

        # Check for not found / invalid
        _not_found = ("no existe", "no registrado", "no encontrado", "inválido")
        if any(kw in body_lower for kw in _not_found):
            result.rfc_status = "No registrado"
            return result

        # Extract taxpayer name
        name_patterns = [
            r"(?:denominaci[oó]n|nombre|raz[oó]n social)[:\s]+([^\n\r]+)",
            r"(?:contribuyente)[:\s]+([^\n\r]+)",
        ]
        for pattern in name_patterns:
            m = re.search(pattern, body_text, re.IGNORECASE)
            if m:
                result.taxpayer_name = m.group(1).strip()
                break

        # Extract RFC status
        status_patterns = [
            r"(?:situaci[oó]n|estatus|status)[:\s]+([^\n\r]+)",
            r"(?:rfc)[:\s]+\w+\s+([^\n\r]+)",
        ]
        for pattern in status_patterns:
            m = re.search(pattern, body_text, re.IGNORECASE)
            if m:
                result.rfc_status = m.group(1).strip()
                break

        if not result.rfc_status:
            if "activo" in body_lower:
                result.rfc_status = "Activo"
            elif "cancelado" in body_lower:
                result.rfc_status = "Cancelado"
            elif "suspendido" in body_lower:
                result.rfc_status = "Suspendido"

        # Extract registration status
        reg_patterns = [
            r"(?:alta|inscripci[oó]n|registro)[:\s]+([^\n\r]+)",
            r"(?:fecha de alta)[:\s]+([^\n\r]+)",
        ]
        for pattern in reg_patterns:
            m = re.search(pattern, body_text, re.IGNORECASE)
            if m:
                result.registration_status = m.group(1).strip()
                break

        result.details = body_text[:500].strip()
        return result
