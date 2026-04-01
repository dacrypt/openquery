"""REPUVE source — Mexican stolen vehicle registry (Registro Publico Vehicular).

Queries REPUVE for vehicle theft status by plate or VIN (NIV).
The portal uses a CAPTCHA.

Flow:
1. Navigate to REPUVE portal
2. Enter plate or NIV
3. Solve CAPTCHA
4. Submit and parse vehicle status
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.repuve import RepuveResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

REPUVE_URL = "https://www2.repuve.gob.mx/"


@register
class RepuveSource(BaseSource):
    """Query Mexican REPUVE stolen vehicle registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.repuve",
            display_name="REPUVE — Registro Vehicular",
            description="Mexican stolen vehicle registry: theft status, make, model, and year",
            country="MX",
            url=REPUVE_URL,
            supported_inputs=[DocumentType.PLATE, DocumentType.VIN],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in (DocumentType.PLATE, DocumentType.VIN):
            raise SourceError("mx.repuve", f"Unsupported document type: {input.document_type}")
        return self._query(
            input.document_number,
            is_vin=(input.document_type == DocumentType.VIN),
            audit=input.audit,
        )

    def _query(self, identifier: str, is_vin: bool = False, audit: bool = False) -> RepuveResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("mx.repuve", "vin" if is_vin else "placa", identifier)

        with browser.page(REPUVE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_selector('input[type="text"]', timeout=15000)
                page.wait_for_timeout(2000)

                # Fill identifier field
                id_input = page.query_selector(
                    'input[name*="placa"], input[name*="niv"], input[name*="vin"], '
                    'input[type="text"]'
                )
                if not id_input:
                    raise SourceError("mx.repuve", "Could not find input field")
                id_input.fill(identifier.upper())
                logger.info("Filled identifier: %s", identifier)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    "button:has-text('Buscar'), button:has-text('Consultar'), "
                    "button:has-text('Verificar')"
                )
                if submit:
                    submit.click()
                else:
                    id_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, identifier, is_vin)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("mx.repuve", f"Query failed: {e}") from e

    def _parse_result(self, page, identifier: str, is_vin: bool) -> RepuveResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        result = RepuveResult(queried_at=datetime.now())
        if is_vin:
            result.niv = identifier.upper()
        else:
            result.placa = identifier.upper()

        # Determine theft status
        if "sin reporte" in body_lower or "no reportado" in body_lower:
            result.estatus_robo = "Sin reporte"
        elif "recuperado" in body_lower:
            result.estatus_robo = "Recuperado"
        elif "con reporte" in body_lower or "reportado" in body_lower or "robo" in body_lower:
            result.estatus_robo = "Con reporte"

        # Parse vehicle details
        field_patterns = [
            (r"(?:marca)[:\s]+([^\n]+)", "marca"),
            (r"(?:modelo|l[ií]nea)[:\s]+([^\n]+)", "modelo"),
            (r"(?:a[nñ]o|modelo\s*a[nñ]o)[:\s]+(\d{4})", "anio"),
            (r"(?:placa|patente)[:\s]+([^\n]+)", "placa"),
            (r"(?:niv|vin)[:\s]+([^\n]+)", "niv"),
        ]

        for pattern, field in field_patterns:
            m = re.search(pattern, body_text, re.IGNORECASE)
            if m and not getattr(result, field):
                setattr(result, field, m.group(1).strip())

        return result
