"""NOSIS source — Argentine credit report (commercial data bureau).

Queries NOSIS for credit score summary and delinquency status by CUIT.

Flow:
1. Navigate to https://www.nosis.com/es
2. Enter CUIT in the search form
3. Parse credit status and delinquency information
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.nosis import NosisResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

NOSIS_URL = "https://www.nosis.com/es"


@register
class NosisSource(BaseSource):
    """Query NOSIS credit bureau for Argentine CUIT credit report summary."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.nosis",
            display_name="NOSIS — Informe Crediticio",
            description="Argentine NOSIS credit bureau: credit status and delinquency summary by CUIT",  # noqa: E501
            country="AR",
            url=NOSIS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cuit = input.extra.get("cuit", "") or input.document_number
        if not cuit:
            raise SourceError(
                "ar.nosis",
                "CUIT required (pass via extra.cuit or document_number)",
            )
        return self._query(cuit.strip(), audit=input.audit)

    def _query(self, cuit: str, audit: bool = False) -> NosisResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ar.nosis", "cuit", cuit)

        with browser.page(NOSIS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill CUIT search field
                cuit_input = page.query_selector(
                    'input[name*="cuit"], input[name*="documento"], '
                    'input[name*="buscar"], input[placeholder*="cuit"], '
                    'input[placeholder*="CUIT"], input[type="text"]'
                )
                if not cuit_input:
                    raise SourceError("ar.nosis", "Could not find CUIT input field")
                cuit_input.fill(cuit)
                logger.info("Filled CUIT: %s", cuit)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    "button:has-text('Buscar'), button:has-text('Consultar'), "
                    "button:has-text('Ver Informe')"
                )
                if submit:
                    submit.click()
                else:
                    cuit_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cuit)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ar.nosis", f"Query failed: {e}") from e

    def _parse_result(self, page, cuit: str) -> NosisResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = NosisResult(queried_at=datetime.now(), cuit=cuit)

        # Company name
        m = re.search(
            r"(?:raz[oó]n social|empresa|nombre)[:\s]+([^\n\r|]{2,80})",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.company_name = m.group(1).strip()

        # Credit status
        m = re.search(
            r"(?:situaci[oó]n crediticia|calificaci[oó]n|estado crediticio)[:\s]+([^\n\r|]{2,60})",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.credit_status = m.group(1).strip()

        # Delinquency — check negative first to avoid false positives
        lower = body_text.lower()
        if any(kw in lower for kw in ("sin mora", "al día", "al dia", "sin deuda")):
            result.delinquency_status = "Sin mora"
        elif any(kw in lower for kw in ("mora", "deuda", "delinquent", "incumplimiento")):
            result.delinquency_status = "Con mora"

        result.details = {"raw_text": body_text[:500]}
        return result
