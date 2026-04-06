"""REPEP source — Mexico do-not-call registry (Registro Público para Evitar Publicidad).

Queries PROFECO's REPEP portal to check if a phone number is registered
on the do-not-call list.

Flow:
1. Navigate to https://repep.profeco.gob.mx/
2. Enter phone number in the search form
3. Parse registration status and date
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.repep import RepepResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

REPEP_URL = "https://repep.profeco.gob.mx/"


@register
class RepepSource(BaseSource):
    """Query PROFECO's REPEP do-not-call registry for a phone number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.repep",
            display_name="REPEP — Registro Público para Evitar Publicidad",
            description="Mexico do-not-call registry: check if a phone number is registered with PROFECO's REPEP",
            country="MX",
            url=REPEP_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        phone = (
            input.extra.get("phone_number", "")
            or input.extra.get("phone", "")
            or input.document_number
        )
        if not phone:
            raise SourceError(
                "mx.repep",
                "Phone number required (pass via extra.phone_number or document_number)",
            )
        return self._query(phone.strip(), audit=input.audit)

    def _query(self, phone_number: str, audit: bool = False) -> RepepResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("mx.repep", "phone_number", phone_number)

        with browser.page(REPEP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill phone number field
                phone_input = page.query_selector(
                    'input[name*="telefono"], input[name*="phone"], '
                    'input[name*="numero"], input[placeholder*="telefono"], '
                    'input[placeholder*="phone"], input[type="tel"], '
                    'input[type="text"]'
                )
                if not phone_input:
                    raise SourceError("mx.repep", "Could not find phone number input field")
                phone_input.fill(phone_number)
                logger.info("Filled phone number: %s", phone_number)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    "button:has-text('Consultar'), button:has-text('Buscar'), "
                    "button:has-text('Verificar')"
                )
                if submit:
                    submit.click()
                else:
                    phone_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, phone_number)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("mx.repep", f"Query failed: {e}") from e

    def _parse_result(self, page, phone_number: str) -> RepepResult:
        import re
        from datetime import datetime

        body_text = page.inner_text("body")
        result = RepepResult(queried_at=datetime.now(), phone_number=phone_number)

        # Check registration status — check negative first to avoid false positives
        lower = body_text.lower()
        if any(kw in lower for kw in ("no registrado", "no inscrito", "not registered", "no está")):
            result.is_registered = False
        elif any(kw in lower for kw in ("registrado", "inscrito", "registered", "sí está")):
            result.is_registered = True

        # Extract registration date if present
        m = re.search(
            r"(?:fecha|date|inscripci[oó]n)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.registration_date = m.group(1).strip()

        result.details = {"raw_text": body_text[:500]}
        return result
