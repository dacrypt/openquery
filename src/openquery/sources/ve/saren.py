"""SAREN source — Venezuela company registry.

Queries the SAREN (Servicio Autónomo de Registros y Notarías) public
consultation portal for company registration information.

Flow:
1. Navigate to SAREN public consultation page
2. Enter company name or RIF
3. Submit and parse registration status, type, inscriptions

Source: https://consultapub.saren.gob.ve/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ve.saren import SarenResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SAREN_URL = "https://consultapub.saren.gob.ve/"


@register
class SarenSource(BaseSource):
    """Query Venezuela company registry (SAREN)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ve.saren",
            display_name="SAREN — Consulta de Empresas",
            description="Venezuela company registry: registration status, type, inscriptions",
            country="VE",
            url=SAREN_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.document_number.strip()
        if not search_term:
            name = input.extra.get("name", "").strip()
            if not name:
                raise SourceError("ve.saren", "Provide a company name or RIF as document_number")
            search_term = name
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SarenResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("ve.saren", "custom", search_term)

        with browser.page(SAREN_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                # Find search input
                search_input = page.query_selector(
                    'input[type="text"][name*="denominacion"], '
                    'input[type="text"][name*="rif"], '
                    'input[type="text"][placeholder*="denominacion"], '
                    'input[type="text"][placeholder*="RIF"], '
                    'input[type="text"][placeholder*="empresa"], '
                    'input[type="search"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("ve.saren", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Querying SAREN for: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="buscar"], button[id*="consultar"], '
                    'a[id*="buscar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ve.saren", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SarenResult:
        """Parse SAREN result page for company registration info."""
        from datetime import datetime

        body_text = page.inner_text("body")

        company_name = ""
        rif = ""
        registration_status = ""
        company_type = ""
        details: dict[str, str] = {}

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped or ":" not in stripped:
                continue
            key, _, val = stripped.partition(":")
            key_lower = key.strip().lower()
            val_clean = val.strip()
            if not val_clean:
                continue

            details[key.strip()] = val_clean

            if any(k in key_lower for k in ["denominacion", "empresa", "razon social", "nombre"]):
                if not company_name:
                    company_name = val_clean
            elif "rif" in key_lower and not rif:
                rif = val_clean
            elif any(k in key_lower for k in ["estado", "estatus", "situacion", "status"]):
                if not registration_status:
                    registration_status = val_clean
            elif any(k in key_lower for k in ["tipo", "clase", "forma juridica"]):
                if not company_type:
                    company_type = val_clean

        # Fallback: try table rows
        if not company_name:
            rows = page.query_selector_all("table tr, .result-row, .item")
            for row in rows:
                text = row.inner_text().strip()
                text_lower = text.lower()
                name_keys = ["denominacion", "empresa", "razon"]
                if any(k in text_lower for k in name_keys) and ":" in text:
                    company_name = text.split(":", 1)[1].strip()
                elif "rif" in text_lower and ":" in text and not rif:
                    rif = text.split(":", 1)[1].strip()
                elif (
                    any(k in text_lower for k in ["estado", "estatus"])
                    and ":" in text
                    and not registration_status
                ):
                    registration_status = text.split(":", 1)[1].strip()
                elif "tipo" in text_lower and ":" in text and not company_type:
                    company_type = text.split(":", 1)[1].strip()

        return SarenResult(
            queried_at=datetime.now(),
            search_term=search_term,
            company_name=company_name,
            rif=rif,
            registration_status=registration_status,
            company_type=company_type,
            details=details,
        )
