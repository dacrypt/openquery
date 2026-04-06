"""Autoridad Fiscalizacion source — Bolivia business supervision (AEMP).

Queries Bolivia AEMP (Autoridad de Empresas) for company registration
status by company name. Browser-based, no CAPTCHA.

URL: https://www.aemp.gob.bo/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.bo.autoridad_fiscalizacion import BoAutoridadFiscalizacionResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

AEMP_URL = "https://www.aemp.gob.bo/"


@register
class BoAutoridadFiscalizacionSource(BaseSource):
    """Query Bolivia AEMP company registration status by company name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="bo.autoridad_fiscalizacion",
            display_name="AEMP — Autoridad de Fiscalización y Control (BO)",
            description="Bolivia AEMP business registration status by company name",
            country="BO",
            url=AEMP_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("company_name", "") or input.document_number
        if not search_term:
            raise SourceError("bo.autoridad_fiscalizacion", "Company name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> BoAutoridadFiscalizacionResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("bo.autoridad_fiscalizacion", "company_name", search_term)

        with browser.page(AEMP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    "input[name*='empresa'], input[name*='buscar'], input[name*='razon'], "
                    "input[id*='empresa'], input[id*='buscar'], "
                    "input[placeholder*='empresa'], input[placeholder*='razón'], "
                    "input[type='text'], input[type='search']"
                )
                if not search_input:
                    raise SourceError(
                        "bo.autoridad_fiscalizacion", "Could not find search input field"
                    )

                search_input.fill(search_term)
                logger.info("Querying AEMP for company: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    "button[type='submit'], input[type='submit'], "
                    "button:has-text('Buscar'), button:has-text('Consultar')"
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

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
                raise SourceError("bo.autoridad_fiscalizacion", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> BoAutoridadFiscalizacionResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = BoAutoridadFiscalizacionResult(
            queried_at=datetime.now(), search_term=search_term
        )

        field_patterns = {
            "empresa": "company_name",
            "razón social": "company_name",
            "denominación": "company_name",
            "estado": "registration_status",
            "estatus": "registration_status",
            "situación": "registration_status",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_patterns.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value and not getattr(result, field):
                        setattr(result, field, value)
                    break

        rows = page.query_selector_all("table tr")
        if len(rows) >= 2:
            cells = rows[1].query_selector_all("td")
            if cells:
                values = [(c.inner_text() or "").strip() for c in cells]
                if len(values) >= 1 and not result.company_name:
                    result.company_name = values[0]
                if len(values) >= 2 and not result.registration_status:
                    result.registration_status = values[1]

        result.details = {"raw": body_text.strip()[:500]}
        return result
