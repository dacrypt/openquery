"""Argentina COPREC source — consumer mediation records.

Queries Argentina consumer defense portal for mediation records by company name.
Browser-based.

Source: https://www.argentina.gob.ar/produccion/defensadelconsumidor/formulario
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.coprec import CoprecResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

COPREC_URL = "https://www.argentina.gob.ar/produccion/defensadelconsumidor/formulario"


@register
class CoprecSource(BaseSource):
    """Query Argentina COPREC consumer defense portal for mediation records."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.coprec",
            display_name="COPREC — Mediación de Consumo (Argentina)",
            description="Argentina COPREC consumer mediation: mediation records by company name",
            country="AR",
            url=COPREC_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("search_term", "") or input.document_number
        if not search_term:
            raise SourceError(
                "ar.coprec",
                "Company name is required (pass via extra.search_term or document_number)",
            )
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> CoprecResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ar.coprec", "search_term", search_term)

        with browser.page(COPREC_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[name*="empresa" i], input[id*="empresa" i], '
                    'input[name*="proveedor" i], input[id*="proveedor" i], '
                    'input[name*="search" i], input[placeholder*="empresa" i], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("ar.coprec", "Could not find company search input field")
                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    "button:has-text('Buscar'), button:has-text('Consultar')"
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ar.coprec", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> CoprecResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = CoprecResult(queried_at=datetime.now(), search_term=search_term)
        details: dict[str, str] = {}

        # Total records — look for numeric count in results
        m = re.search(
            r"(\d+)\s*(?:resultado|mediaci[oó]n|caso|registro)",
            body_text,
            re.IGNORECASE,
        )
        if m:
            try:
                result.total_records = int(m.group(1))
            except ValueError:
                pass

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

            # Company name
            if any(k in lower for k in ("empresa", "proveedor", "razón social", "razon social")):
                if ":" in stripped and not result.company_name:
                    result.company_name = stripped.split(":", 1)[1].strip()

        if not result.company_name:
            result.company_name = search_term

        result.details = details
        return result
