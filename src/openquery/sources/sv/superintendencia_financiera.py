"""Superintendencia Financiera source — El Salvador SSF banking statistics.

Queries the Superintendencia del Sistema Financiero (SSF) of El Salvador
for financial statistics.

Source: https://www.ssf.gob.sv/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.sv.superintendencia_financiera import SvSuperintendenciaFinancieraResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SV_SSF_ESTADISTICAS_URL = "https://www.ssf.gob.sv/"


@register
class SvSuperintendenciaFinancieraSource(BaseSource):
    """Query El Salvador SSF financial statistics by indicator."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="sv.superintendencia_financiera",
            display_name="SSF — Estadísticas Financieras",
            description=(
                "El Salvador SSF: banking and financial institution statistics by indicator"
            ),
            country="SV",
            url=SV_SSF_ESTADISTICAS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        indicator = input.extra.get("indicator", "") or input.document_number.strip()
        if not indicator:
            raise SourceError("sv.superintendencia_financiera", "Indicator is required")
        return self._query(indicator=indicator, audit=input.audit)

    def _query(self, indicator: str, audit: bool = False) -> SvSuperintendenciaFinancieraResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("sv.superintendencia_financiera", "indicator", indicator)

        with browser.page(SV_SSF_ESTADISTICAS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[name*="indicador"], input[id*="indicador"], '
                    'input[type="search"], input[type="text"], '
                    'input[name*="search"], input[name*="banco"]'
                )
                if search_input:
                    search_input.fill(indicator)
                    logger.info("Querying SV SSF for indicator: %s", indicator)

                    submit_btn = page.query_selector(
                        'button[type="submit"], input[type="submit"], '
                        'button:has-text("Consultar"), button:has-text("Buscar")'
                    )
                    if submit_btn:
                        submit_btn.click()
                    else:
                        search_input.press("Enter")

                    page.wait_for_timeout(4000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, indicator)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("sv.superintendencia_financiera", f"Query failed: {e}") from e

    def _parse_result(self, page, indicator: str) -> SvSuperintendenciaFinancieraResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        indicator_name = ""
        value = ""
        period = ""
        institution = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if any(kw in lower for kw in ["indicador", "descripción"]) and ":" in stripped and not indicator_name:  # noqa: E501
                indicator_name = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["valor", "dato", "cifra"]) and ":" in stripped and not value:  # noqa: E501
                value = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["período", "fecha", "año"]) and ":" in stripped and not period:  # noqa: E501
                period = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["institución", "banco", "entidad"]) and ":" in stripped and not institution:  # noqa: E501
                institution = stripped.split(":", 1)[1].strip()

        return SvSuperintendenciaFinancieraResult(
            queried_at=datetime.now(),
            indicator=indicator,
            indicator_name=indicator_name,
            value=value,
            period=period,
            institution=institution,
            details=body_text.strip()[:500],
        )
