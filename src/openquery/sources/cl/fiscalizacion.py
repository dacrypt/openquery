"""Fiscalizacion source — Chilean traffic infractions by plate.

Queries the Chilean vehicle inspection / traffic citation system.
The portal uses a simple CAPTCHA.

Flow:
1. Navigate to fiscalizacion portal
2. Enter plate (patente)
3. Solve simple CAPTCHA
4. Submit and parse infraction list
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.fiscalizacion import FiscalizacionResult, InfraccionTransito
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

FISCALIZACION_URL = "https://rrvv.fiscalizacion.cl/"


@register
class FiscalizacionSource(BaseSource):
    """Query Chilean traffic infractions by plate (patente)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.fiscalizacion",
            display_name="Fiscalizacion — Infracciones de Transito",
            description="Chilean traffic infractions and citations by plate number",
            country="CL",
            url=FISCALIZACION_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        raise SourceError("cl.fiscalizacion", "Source deprecated: site unreachable since 2026-04")
        if input.document_type != DocumentType.PLATE:
            raise SourceError("cl.fiscalizacion", f"Unsupported document type: {input.document_type}")
        return self._query(input.document_number, audit=input.audit)

    def _query(self, patente: str, audit: bool = False) -> FiscalizacionResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("cl.fiscalizacion", "placa", patente)

        with browser.page(FISCALIZACION_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill plate number
                plate_input = page.query_selector(
                    'input[name*="patente"], input[name*="placa"], input[type="text"]'
                )
                if not plate_input:
                    raise SourceError("cl.fiscalizacion", "Could not find plate input field")
                plate_input.fill(patente.upper())
                logger.info("Filled patente: %s", patente)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    "button:has-text('Buscar'), button:has-text('Consultar')"
                )
                if submit:
                    submit.click()
                else:
                    plate_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, patente)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("cl.fiscalizacion", f"Query failed: {e}") from e

    def _parse_result(self, page, patente: str) -> FiscalizacionResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = FiscalizacionResult(queried_at=datetime.now(), patente=patente.upper())

        # Parse infraction table rows
        rows = page.query_selector_all("table tr, .infracciones tr, .resultado tr")

        infracciones: list[InfraccionTransito] = []
        for row in rows[1:]:  # skip header
            cells = row.query_selector_all("td")
            if len(cells) >= 3:
                values = [(c.inner_text() or "").strip() for c in cells]
                infraccion = InfraccionTransito(
                    fecha=values[0] if len(values) > 0 else "",
                    tipo=values[1] if len(values) > 1 else "",
                    monto=values[2] if len(values) > 2 else "",
                    estado=values[3] if len(values) > 3 else "",
                    comuna=values[4] if len(values) > 4 else "",
                )
                infracciones.append(infraccion)

        result.infracciones = infracciones
        result.total_infracciones = len(infracciones)

        # Try to extract total from page text
        m = re.search(r"(\d+)\s*(?:infracci[oó]n|resultado|registro)", body_text, re.IGNORECASE)
        if m:
            result.total_infracciones = max(result.total_infracciones, int(m.group(1)))

        return result
