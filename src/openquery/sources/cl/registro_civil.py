"""Registro Civil source — Chilean document validity check (SIDIV).

Queries Chile's Registro Civil SIDIV portal for document validity
(RUN + serial number). Browser-based, public, no login required.

URL: https://portal.sidiv.registrocivil.cl/usuarios-portal/pages/DocumentRequestStatus.xhtml
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.registro_civil import RegistroCivilResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

REGISTRO_CIVIL_URL = (
    "https://portal.sidiv.registrocivil.cl/usuarios-portal/pages/DocumentRequestStatus.xhtml"
)


@register
class RegistroCivilSource(BaseSource):
    """Query Chilean document validity via Registro Civil SIDIV portal."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.registro_civil",
            display_name="Registro Civil — Validez de Documento (SIDIV)",
            description="Chilean document validity check by RUN + serial number",
            country="CL",
            url=REGISTRO_CIVIL_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        run = input.extra.get("run", "") or input.document_number
        serial_number = input.extra.get("serial_number", "")
        if not run:
            raise SourceError(
                "cl.registro_civil", "RUN is required (pass via extra.run or document_number)"
            )
        if not serial_number:
            raise SourceError(
                "cl.registro_civil", "Serial number is required (pass via extra.serial_number)"
            )
        return self._query(run, serial_number, audit=input.audit)

    def _query(self, run: str, serial_number: str, audit: bool = False) -> RegistroCivilResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("cl.registro_civil", "run", run)

        with browser.page(REGISTRO_CIVIL_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill RUN
                run_input = page.query_selector(
                    'input[id*="run"], input[name*="run"], '
                    'input[id*="RUN"], input[name*="RUN"], '
                    'input[placeholder*="RUN"], input[placeholder*="12.345"]'
                )
                if not run_input:
                    raise SourceError("cl.registro_civil", "Could not find RUN input field")
                run_input.fill(run)
                logger.info("Filled RUN: %s", run)

                # Fill serial number
                serial_input = page.query_selector(
                    'input[id*="serial"], input[name*="serial"], '
                    'input[id*="numero"], input[name*="numero"], '
                    'input[placeholder*="serie"], input[placeholder*="Serie"]'
                )
                if not serial_input:
                    raise SourceError(
                        "cl.registro_civil", "Could not find serial number input field"
                    )
                serial_input.fill(serial_number)
                logger.info("Filled serial number: %s", serial_number)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    "button:has-text('Consultar'), button:has-text('Verificar'), "
                    "button:has-text('Buscar')"
                )
                if submit:
                    submit.click()
                else:
                    serial_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, run, serial_number)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("cl.registro_civil", f"Query failed: {e}") from e

    def _parse_result(self, page, run: str, serial_number: str) -> RegistroCivilResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = RegistroCivilResult(
            queried_at=datetime.now(),
            run=run,
            serial_number=serial_number,
        )

        # Parse document status — check negative cases before VIGENTE
        if re.search(r"no\s+vigente|bloqueado|anulado|vencido", body_text, re.IGNORECASE):
            result.document_status = "NO VIGENTE"
        elif re.search(r"\bVIGENTE\b", body_text, re.IGNORECASE):
            result.document_status = "VIGENTE"

        # Try table-based parsing
        rows = page.query_selector_all("table tr, .resultado tr, .estado-documento tr")
        details: dict = {}
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip()
                value = (cells[1].inner_text() or "").strip()
                if label and value:
                    details[label] = value
                    label_lower = label.lower()
                    if "estado" in label_lower and not result.document_status:
                        result.document_status = value

        if details:
            result.details = details

        return result
