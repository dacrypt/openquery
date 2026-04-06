"""Profeco source — Mexican consumer complaints (Buró Comercial Profeco).

Queries the Profeco Buró Comercial portal for consumer complaint statistics
by company/provider name.

Flow:
1. Navigate to https://burocomercial.profeco.gob.mx/
2. Search by provider/company name
3. Parse complaint counts and conciliation outcomes
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.profeco import ProfecoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

PROFECO_URL = "https://burocomercial.profeco.gob.mx/"


@register
class ProfecoSource(BaseSource):
    """Query Mexican Profeco Buró Comercial for consumer complaints and conciliation outcomes."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.profeco",
            display_name="Profeco — Buró Comercial",
            description="Mexican Profeco consumer complaints: counts and conciliation outcomes",
            country="MX",
            url=PROFECO_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        provider = input.extra.get("provider_name", "") or input.document_number
        if not provider:
            raise SourceError(
                "mx.profeco",
                "Provider name is required (pass via extra.provider_name or document_number)",
            )
        return self._query(provider.strip(), audit=input.audit)

    def _query(self, provider: str, audit: bool = False) -> ProfecoResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("mx.profeco", "provider_name", provider)

        with browser.page(PROFECO_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill provider search field
                search_input = page.query_selector(
                    'input[name*="proveedor"], input[name*="empresa"], '
                    'input[placeholder*="proveedor"], input[placeholder*="busca"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("mx.profeco", "Could not find provider search field")
                search_input.fill(provider)
                logger.info("Filled provider: %s", provider)

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
                    search_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, provider)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("mx.profeco", f"Query failed: {e}") from e

    def _parse_result(self, page, provider: str) -> ProfecoResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = ProfecoResult(queried_at=datetime.now(), provider_name=provider)

        # Extract total complaints
        m = re.search(
            r"(?:queja|reclamaci[oó]n|denuncia|complaint)[s\w]*[:\s]+(\d[\d,\.]*)"
            r"|(\d[\d,\.]*)\s*(?:queja|reclamaci[oó]n|denuncia|complaint)",
            body_text,
            re.IGNORECASE,
        )
        if m:
            raw = (m.group(1) or m.group(2) or "").replace(",", "").replace(".", "")
            try:
                result.total_complaints = int(raw)
            except ValueError:
                pass

        # Extract resolved count
        m = re.search(r"(\d[\d,\.]*)\s*(?:resuelto|concluido|favorable)", body_text, re.IGNORECASE)
        if not m:
            m = re.search(r"(?:resuelto|concluido)[:\s]+(\d[\d,\.]*)", body_text, re.IGNORECASE)
        if m:
            raw = m.group(1).replace(",", "").replace(".", "")
            try:
                result.resolved = int(raw)
            except ValueError:
                pass

        # Extract conciliation rate
        m = re.search(
            r"(\d{1,3}(?:[.,]\d+)?)\s*%\s*(?:conciliaci[oó]n|conciliado|acuerdo)",
            body_text,
            re.IGNORECASE,
        )
        if not m:
            m = re.search(
                r"(?:conciliaci[oó]n|conciliado)[:\s]+(\d{1,3}(?:[.,]\d+)?)\s*%",
                body_text,
                re.IGNORECASE,
            )
        if m:
            result.conciliation_rate = f"{m.group(1)}%"

        # Extract sector
        m = re.search(r"(?:sector|giro|rubro)[:\s]+([^\n\r]+)", body_text, re.IGNORECASE)
        if m:
            result.sector = m.group(1).strip()

        result.details = body_text[:500].strip()
        return result
