"""SENIAT source — Venezuela RIF tax registry lookup.

Queries the SENIAT (Servicio Nacional Integrado de Administración Aduanera y Tributaria)
contributor search page for a RIF number.

Flow:
1. Navigate to SENIAT BuscaRif page
2. Solve image CAPTCHA
3. Enter RIF number and submit
4. Parse taxpayer name, tax status, and taxpayer type

Source: http://contribuyente.seniat.gob.ve/BuscaRif/BuscaRif.jsp
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ve.seniat import SeniatResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SENIAT_URL = "http://contribuyente.seniat.gob.ve/BuscaRif/BuscaRif.jsp"


@register
class SeniatSource(BaseSource):
    """Query Venezuela SENIAT RIF tax registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ve.seniat",
            display_name="SENIAT — Consulta RIF",
            description=(
                "Venezuela SENIAT tax registry: taxpayer name, tax status, and taxpayer type by RIF"
            ),
            country="VE",
            url=SENIAT_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=5,
        )

    def query(self, input: QueryInput) -> BaseModel:
        rif = input.extra.get("rif", "") or input.document_number.strip()
        if not rif:
            raise SourceError(
                "ve.seniat", "RIF number is required (use extra.rif or document_number)"
            )
        return self._query(rif=rif, audit=input.audit)

    def _query(self, rif: str, audit: bool = False) -> SeniatResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ve.seniat", "custom", rif)

        with browser.page(SENIAT_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                # Locate RIF input field
                rif_input = page.query_selector(
                    'input[name*="rif"], input[name*="RIF"], '
                    'input[id*="rif"], input[id*="RIF"], '
                    'input[type="text"]'
                )
                if not rif_input:
                    raise SourceError("ve.seniat", "Could not find RIF input field")

                rif_input.fill(rif)
                logger.info("Querying SENIAT for RIF: %s", rif)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit form
                submit_btn = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'input[value*="Buscar"], input[value*="Consultar"], '
                    'button:has-text("Buscar")'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    rif_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, rif)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ve.seniat", f"Query failed: {e}") from e

    def _parse_result(self, page, rif: str) -> SeniatResult:
        """Parse SENIAT result page for taxpayer information."""
        from datetime import datetime

        body_text = page.inner_text("body")
        details: dict[str, str] = {}

        taxpayer_name = ""
        tax_status = ""
        taxpayer_type = ""

        # Parse key:value lines from page body
        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped or ":" not in stripped:
                continue
            key, _, val = stripped.partition(":")
            key_clean = key.strip()
            val_clean = val.strip()
            if not val_clean:
                continue

            details[key_clean] = val_clean
            key_lower = key_clean.lower()

            if any(k in key_lower for k in ("nombre", "razon", "denominacion")):
                if not taxpayer_name:
                    taxpayer_name = val_clean
            elif any(k in key_lower for k in ("estado", "status", "estatus", "condicion")):
                if not tax_status:
                    tax_status = val_clean
            elif any(k in key_lower for k in ("tipo", "contribuyente", "categoria")):
                if not taxpayer_type:
                    taxpayer_type = val_clean

        # Fallback: try regex patterns on full body
        if not taxpayer_name:
            m = re.search(
                r"(?:Nombre|Raz[oó]n Social|Denominaci[oó]n)[:\s]+([^\n]+)",
                body_text,
                re.IGNORECASE,
            )
            if m:
                taxpayer_name = m.group(1).strip()

        if not tax_status:
            m = re.search(
                r"(?:Estado|Estatus|Condici[oó]n)[:\s]+([^\n]+)",
                body_text,
                re.IGNORECASE,
            )
            if m:
                tax_status = m.group(1).strip()

        if not taxpayer_type:
            m = re.search(
                r"(?:Tipo|Contribuyente|Categor[íi]a)[:\s]+([^\n]+)",
                body_text,
                re.IGNORECASE,
            )
            if m:
                taxpayer_type = m.group(1).strip()

        return SeniatResult(
            queried_at=datetime.now(),
            rif=rif,
            taxpayer_name=taxpayer_name,
            tax_status=tax_status,
            taxpayer_type=taxpayer_type,
            details=details,
        )
