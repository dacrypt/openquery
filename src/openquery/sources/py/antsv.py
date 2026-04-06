"""Paraguay ANTSV source — vehicle tax value lookup.

Queries the Agencia Nacional de Tránsito y Seguridad Vial (ANTSV) for
vehicle taxable value and tax amount by brand, model, and year.

Source: https://ruhr.antsv.gov.py/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.py.antsv import PyAntsvResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ANTSV_URL = "https://ruhr.antsv.gov.py/"


@register
class PyAntsvSource(BaseSource):
    """Query Paraguayan ANTSV vehicle tax value by brand, model, and year."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="py.antsv",
            display_name="ANTSV — Valor Impositivo Vehicular",
            description="Paraguay vehicle taxable value and tax amount by brand/model/year (ANTSV)",
            country="PY",
            url=ANTSV_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        brand = input.extra.get("brand", "") or input.extra.get("marca", "")
        model = input.extra.get("model", "") or input.extra.get("modelo", "")
        year = input.extra.get("year", "") or input.extra.get("anio", "") or input.document_number
        if not brand and not model and not year:
            raise SourceError("py.antsv", "At least one of brand, model, or year is required")
        return self._query(brand.strip(), model.strip(), str(year).strip(), audit=input.audit)

    def _query(self, brand: str, model: str, year: str, audit: bool = False) -> PyAntsvResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("py.antsv", "custom", f"{brand}_{model}_{year}")

        with browser.page(ANTSV_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if brand:
                    brand_input = page.query_selector(
                        'input[name*="marca"], input[id*="marca"], '
                        'input[name*="brand"], input[id*="brand"]'
                    )
                    if brand_input:
                        brand_input.fill(brand)
                        logger.info("Filled brand: %s", brand)

                if model:
                    model_input = page.query_selector(
                        'input[name*="modelo"], input[id*="modelo"], '
                        'input[name*="model"], input[id*="model"]'
                    )
                    if model_input:
                        model_input.fill(model)
                        logger.info("Filled model: %s", model)

                if year:
                    year_input = page.query_selector(
                        'input[name*="anio"], input[id*="anio"], '
                        'input[name*="year"], input[id*="year"], '
                        'input[name*="año"], select[name*="anio"]'
                    )
                    if year_input:
                        tag = year_input.evaluate("el => el.tagName.toLowerCase()")
                        if tag == "select":
                            page.select_option(
                                'select[name*="anio"], select[id*="anio"]',
                                value=year,
                            )
                        else:
                            year_input.fill(year)
                        logger.info("Filled year: %s", year)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar")'
                )
                if submit:
                    submit.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, brand, model, year)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("py.antsv", f"Query failed: {e}") from e

    def _parse_result(self, page, brand: str, model: str, year: str) -> PyAntsvResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = PyAntsvResult(queried_at=datetime.now(), brand=brand, model=model, year=year)

        field_map = {
            "valor imponible": "taxable_value",
            "valor impositivo": "taxable_value",
            "impuesto": "tax_amount",
            "monto": "tax_amount",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and (":" in stripped or "\t" in stripped):
                    sep = ":" if ":" in stripped else "\t"
                    value = stripped.split(sep, 1)[1].strip()
                    if value:
                        setattr(result, field, value)
                    break

        if body_text.strip():
            result.details = body_text.strip()[:500]

        return result
