"""Policia Nacional source — Colombian judicial background records.

Queries the Policia Nacional DIJIN for judicial background records.

Flow:
1. Navigate to https://antecedentes.policia.gov.co:7005/WebJudicial/
2. Accept terms of use (JSF form)
3. Enter cedula number
4. Submit and parse result
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.policia import PoliciaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

POLICIA_URL = "https://antecedentes.policia.gov.co:7005/WebJudicial/"


@register
class PoliciaSource(BaseSource):
    """Query Colombian judicial background records (Policia Nacional)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.policia",
            display_name="Policia Nacional — Antecedentes Judiciales",
            description="Colombian judicial background and criminal records (DIJIN)",
            country="CO",
            url=POLICIA_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError(
                "co.policia",
                f"Only cedula queries supported, got: {input.document_type}",
            )
        return self._query(input.document_number, audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> PoliciaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.policia", "cedula", cedula)

        with browser.page(POLICIA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                # Step 1: Accept terms — JSF form with radio buttons
                page.wait_for_selector("#continuarBtn, #aceptaOption\\:0", timeout=15000)

                # Select "Acepto" radio and submit
                page.check("#aceptaOption\\:0")
                page.click("#continuarBtn")
                logger.info("Accepted terms of use")

                # Wait for the query form to appear
                page.wait_for_selector(
                    'input[type="text"], #cedula, #documento',
                    timeout=15000,
                )
                page.wait_for_timeout(2000)

                # Step 2: Fill cedula — find the text input
                cedula_input = page.query_selector(
                    'input[type="text"][id*="cedula"], '
                    'input[type="text"][id*="documento"], '
                    'input[type="text"][name*="cedula"], '
                    'input[type="text"][name*="documento"], '
                    'input[type="text"]'
                )
                if not cedula_input:
                    raise SourceError("co.policia", "Could not find cedula input field")

                cedula_input.fill(cedula)
                logger.info("Filled cedula: %s", cedula)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Step 3: Submit the query
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    cedula_input.press("Enter")

                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                # Step 4: Parse result
                result = self._parse_result(page, cedula)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.policia", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> PoliciaResult:
        """Parse the result page."""
        from datetime import datetime

        body_text = page.inner_text("body")

        no_records = any(phrase in body_text.lower() for phrase in [
            "no tiene asuntos pendientes",
            "no registra",
            "no aparece",
            "su cédula de ciudadanía no registra",
        ])

        has_records = any(phrase in body_text.lower() for phrase in [
            "registra antecedentes",
            "tiene asuntos pendientes",
            "anotacion",
        ]) and not no_records

        mensaje = ""
        if no_records:
            mensaje = "No tiene asuntos pendientes con las autoridades judiciales"
        elif has_records:
            mensaje = "Registra antecedentes judiciales"

        return PoliciaResult(
            queried_at=datetime.now(),
            cedula=cedula,
            tiene_antecedentes=has_records,
            mensaje=mensaje,
        )
