"""Chile SII boleta source — invoice/boleta verification.

Queries SII portal to verify boleta/invoice validity by RUT and folio number.
Browser-based.

Source: https://www.sii.cl/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.sii_boleta import SiiBoletaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SII_BOLETA_URL = "https://www.sii.cl/servicios_online/1047-.html"


@register
class SiiBoletaSource(BaseSource):
    """Query SII to verify boleta/invoice validity."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.sii_boleta",
            display_name="SII — Verificación de Boleta/Factura",
            description="Chile SII boleta/invoice verification: validity, amount, and date by RUT and folio",  # noqa: E501
            country="CL",
            url=SII_BOLETA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        rut = input.extra.get("rut", "") or input.document_number
        folio = input.extra.get("folio", "")
        if not rut:
            raise SourceError("cl.sii_boleta", "RUT is required (pass via extra.rut)")
        if not folio:
            raise SourceError("cl.sii_boleta", "Folio number is required (pass via extra.folio)")
        return self._query(rut.strip(), folio.strip(), audit=input.audit)

    def _query(self, rut: str, folio: str, audit: bool = False) -> SiiBoletaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cl.sii_boleta", "rut", rut)

        with browser.page(SII_BOLETA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill RUT
                rut_input = page.query_selector(
                    'input[name*="rut" i], input[id*="rut" i], '
                    'input[placeholder*="rut" i], input[type="text"]:first-of-type'
                )
                if not rut_input:
                    raise SourceError("cl.sii_boleta", "Could not find RUT input field")
                rut_input.fill(rut)
                logger.info("Filled RUT: %s", rut)

                # Fill folio
                folio_input = page.query_selector(
                    'input[name*="folio" i], input[id*="folio" i], '
                    'input[placeholder*="folio" i]'
                )
                if folio_input:
                    folio_input.fill(folio)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    "button:has-text('Consultar'), button:has-text('Verificar')"
                )
                if submit:
                    submit.click()
                else:
                    rut_input.press("Enter")

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, rut, folio)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("cl.sii_boleta", f"Query failed: {e}") from e

    def _parse_result(self, page, rut: str, folio: str) -> SiiBoletaResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        lower_body = body_text.lower()
        result = SiiBoletaResult(queried_at=datetime.now(), rut=rut, folio=folio)
        details: dict[str, str] = {}

        # Validity detection — check negative patterns first
        if any(k in lower_body for k in ("no válida", "no valida", "inválida", "invalida")):
            result.boleta_valid = False
        elif any(k in lower_body for k in ("válida", "valida", "vigente", "verificada")):
            result.boleta_valid = True

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue

            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val

            # Amount
            if any(k in lower for k in ("monto", "valor", "total")) and not result.amount:
                if ":" in stripped:
                    result.amount = stripped.split(":", 1)[1].strip()

            # Date
            if any(k in lower for k in ("fecha", "date")) and not result.date:
                if ":" in stripped:
                    result.date = stripped.split(":", 1)[1].strip()

        result.details = details
        return result
