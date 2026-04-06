"""Registro Nacional source — Costa Rica company lookup.

Queries Costa Rica's Registro Nacional (RNP Digital) for company data
by cedula juridica.

Source: https://www.rnpdigital.com/personas_juridicas/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cr.registro_nacional import CrRegistroNacionalResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

REGISTRO_NACIONAL_URL = "https://www.rnpdigital.com/personas_juridicas/"


@register
class CrRegistroNacionalSource(BaseSource):
    """Query Costa Rica Registro Nacional company data by cedula juridica."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cr.registro_nacional",
            display_name="Registro Nacional — Personas Jurídicas",
            description=(
                "Costa Rica Registro Nacional: company name, status, and legal representative by cedula juridica"  # noqa: E501
            ),
            country="CR",
            url=REGISTRO_NACIONAL_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("cedula_juridica", "")
            or input.extra.get("company_name", "")
            or input.document_number.strip()
        )
        if not search_term:
            raise SourceError("cr.registro_nacional", "Cedula juridica or company name is required")
        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> CrRegistroNacionalResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cr.registro_nacional", "search_term", search_term)

        with browser.page(REGISTRO_NACIONAL_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[name*="cedula"], input[name*="search"], '
                    'input[id*="cedula"], input[id*="search"], '
                    'input[placeholder*="cédula"], input[placeholder*="empresa"], '
                    'input[type="search"], input[type="text"]'
                )
                if not search_input:
                    raise SourceError("cr.registro_nacional", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Querying Registro Nacional for: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button:has-text("Consultar"), button:has-text("Buscar"), '
                    'input[value*="Consultar"], input[value*="Buscar"]'
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
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("cr.registro_nacional", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> CrRegistroNacionalResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        company_name = ""
        cedula_juridica = ""
        status = ""
        legal_representative = ""

        field_map = {
            "razón social": "company_name",
            "razon social": "company_name",
            "nombre": "company_name",
            "cédula jurídica": "cedula_juridica",
            "cedula juridica": "cedula_juridica",
            "estado": "status",
            "representante legal": "legal_representative",
            "representante": "legal_representative",
            "agente residente": "legal_representative",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        if field == "company_name" and not company_name:
                            company_name = value
                        elif field == "cedula_juridica" and not cedula_juridica:
                            cedula_juridica = value
                        elif field == "status" and not status:
                            status = value
                        elif field == "legal_representative" and not legal_representative:
                            legal_representative = value
                    break

        return CrRegistroNacionalResult(
            queried_at=datetime.now(),
            search_term=search_term,
            company_name=company_name,
            cedula_juridica=cedula_juridica,
            status=status,
            legal_representative=legal_representative,
            details=body_text.strip()[:500],
        )
