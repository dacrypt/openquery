"""IVSS source — Venezuela social security.

Queries the IVSS (Instituto Venezolano de los Seguros Sociales) public
consultation portal for social security enrollment and contribution status.

Flow:
1. Navigate to IVSS constancia de cotización page
2. Enter cedula number
3. Submit and parse enrollment status, contribution certificate status, employer

Note: The service runs on non-standard port 28088 and may have availability
issues due to infrastructure constraints.

Source: http://www.ivss.gob.ve:28088/ConstanciaCotizacion/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ve.ivss import IvssResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

IVSS_URL = "http://www.ivss.gob.ve:28088/ConstanciaCotizacion/"


@register
class IvssSource(BaseSource):
    """Query Venezuela social security enrollment by cedula (IVSS)."""

    def __init__(self, timeout: float = 45.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ve.ivss",
            display_name="IVSS — Constancia de Cotización",
            description=(
                "Venezuela social security: enrollment status, contribution certificate, employer"
            ),
            country="VE",
            url=IVSS_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=5,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError(
                "ve.ivss",
                f"Unsupported document type: {input.document_type}. Use cedula.",
            )
        cedula = input.document_number.strip()
        if not cedula:
            raise SourceError("ve.ivss", "cedula is required")
        return self._query(cedula, audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> IvssResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("ve.ivss", "cedula", cedula)

        with browser.page(IVSS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=20000)
                page.wait_for_timeout(2000)

                # Find cedula input field
                cedula_input = page.query_selector(
                    'input[name*="cedula"], input[name*="ci"], '
                    'input[id*="cedula"], input[id*="ci"], '
                    'input[placeholder*="cedula"], input[placeholder*="Cedula"], '
                    'input[placeholder*="cédula"], '
                    'input[type="text"]'
                )
                if not cedula_input:
                    raise SourceError("ve.ivss", "Could not find cedula input field")

                # Strip any V/E prefix for numeric-only fields
                cedula_upper = cedula.upper()
                if cedula_upper.startswith(("V", "E")):
                    number = cedula_upper[1:].lstrip("-").strip()
                else:
                    number = cedula.strip()

                cedula_input.fill(number)
                logger.info("Querying IVSS for cedula: %s", cedula)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit form
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'input[value*="Consultar"], input[value*="Buscar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    cedula_input.press("Enter")

                page.wait_for_timeout(6000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cedula)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ve.ivss", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> IvssResult:
        """Parse IVSS result page for social security enrollment info."""
        from datetime import datetime

        body_text = page.inner_text("body")

        enrollment_status = ""
        contribution_status = ""
        employer = ""
        details: dict[str, str] = {}

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped or ":" not in stripped:
                continue
            key, _, val = stripped.partition(":")
            key_lower = key.strip().lower()
            val_clean = val.strip()
            if not val_clean:
                continue

            details[key.strip()] = val_clean

            if any(k in key_lower for k in ["inscripcion", "afiliacion", "asegurado", "estatus"]):
                if not enrollment_status:
                    enrollment_status = val_clean
            elif any(k in key_lower for k in ["cotizacion", "constancia", "aporte", "pago"]):
                if not contribution_status:
                    contribution_status = val_clean
            elif any(k in key_lower for k in ["patrono", "empleador", "empresa", "empleado"]):
                if not employer:
                    employer = val_clean

        # Fallback: try table rows
        if not enrollment_status:
            rows = page.query_selector_all("table tr, .result-row, .item")
            for row in rows:
                text = row.inner_text().strip()
                text_lower = text.lower()
                if (
                    any(k in text_lower for k in ["inscripcion", "afiliacion", "estatus"])
                    and ":" in text
                    and not enrollment_status
                ):
                    enrollment_status = text.split(":", 1)[1].strip()
                elif (
                    any(k in text_lower for k in ["cotizacion", "constancia"])
                    and ":" in text
                    and not contribution_status
                ):
                    contribution_status = text.split(":", 1)[1].strip()
                elif (
                    any(k in text_lower for k in ["patrono", "empleador"])
                    and ":" in text
                    and not employer
                ):
                    employer = text.split(":", 1)[1].strip()

        return IvssResult(
            queried_at=datetime.now(),
            cedula=cedula,
            enrollment_status=enrollment_status,
            contribution_status=contribution_status,
            employer=employer,
            details=details,
        )
