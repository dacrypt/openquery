"""SII RUT source — Chilean taxpayer registry (Servicio de Impuestos Internos).

Queries SII for taxpayer information by RUT.
The portal uses an image CAPTCHA.

Flow:
1. Navigate to SII verification page
2. Enter RUT
3. Solve image CAPTCHA
4. Submit and parse result
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.sii_rut import SiiRutResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SII_URL = "https://www2.sii.cl/stc/noauthz"


@register
class SiiRutSource(BaseSource):
    """Query Chilean taxpayer registry (SII) by RUT."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.sii_rut",
            display_name="SII — Verificacion de RUT",
            description="Chilean taxpayer registry: business name, economic activities, and status",
            country="CL",
            url=SII_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        rut = input.extra.get("rut", "") or input.document_number
        if not rut:
            raise SourceError("cl.sii_rut", "RUT is required (pass via extra.rut)")
        return self._query(rut, audit=input.audit)

    def _query(self, rut: str, audit: bool = False) -> SiiRutResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("cl.sii_rut", "rut", rut)

        with browser.page(SII_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_selector('input[type="text"]', timeout=15000)
                page.wait_for_timeout(2000)

                # Fill RUT
                rut_input = page.query_selector(
                    'input[name*="rut"], input[name*="RUT"], input[type="text"]'
                )
                if not rut_input:
                    raise SourceError("cl.sii_rut", "Could not find RUT input field")
                rut_input.fill(rut)
                logger.info("Filled RUT: %s", rut)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit form
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
                raise SourceError("cl.sii_rut", f"Query failed: {e}") from e

    def _parse_result(self, page, rut: str) -> SiiRutResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        result = SiiRutResult(queried_at=datetime.now(), rut=rut)

        # Parse razon social
        m = re.search(r"(?:raz[oó]n\s*social|nombre)[:\s]+([^\n]+)", body_text, re.IGNORECASE)
        if m:
            result.razon_social = m.group(1).strip()

        # Parse actividades economicas
        actividades = re.findall(
            r"actividad[:\s]+([^\n]+)", body_text, re.IGNORECASE,
        )
        if actividades:
            result.actividades_economicas = [a.strip() for a in actividades]

        # Parse estado
        m = re.search(r"(?:estado|situaci[oó]n)[:\s]+([^\n]+)", body_text, re.IGNORECASE)
        if m:
            result.estado = m.group(1).strip()

        # Parse fecha inicio actividades
        m = re.search(r"inicio\s*(?:de\s*)?actividades[:\s]+([^\n]+)", body_text, re.IGNORECASE)
        if m:
            result.fecha_inicio_actividades = m.group(1).strip()

        # Parse tipo contribuyente
        m = re.search(r"tipo\s*(?:de\s*)?contribuyente[:\s]+([^\n]+)", body_text, re.IGNORECASE)
        if m:
            result.tipo_contribuyente = m.group(1).strip()

        return result
