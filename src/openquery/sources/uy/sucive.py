"""Uruguay SUCIVE source — vehicle patent/tax lookup.

Queries SUCIVE (Sistema Único de Cobro de Ingresos Vehiculares) for
vehicle patent, debt, and circulation status.

Source: https://sucive.gub.uy/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.uy.sucive import UySuciveResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

# Navigate directly to the consultation form (homepage has no form)
SUCIVE_URL = "https://sucive.gub.uy/consulta_patente"


@register
class UySuciveSource(BaseSource):
    """Query Uruguayan vehicle patent/tax registry (SUCIVE)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="uy.sucive",
            display_name="SUCIVE — Patente Vehicular",
            description="Uruguayan vehicle patent, debt, and circulation status (SUCIVE)",
            country="UY",
            url=SUCIVE_URL,
            supported_inputs=[DocumentType.PLATE, DocumentType.CUSTOM],
            requires_captcha=True,  # reCAPTCHA v2 Enterprise
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        matricula = input.extra.get("matricula", "") or input.document_number
        padron = input.extra.get("padron", "")
        departamento = input.extra.get("departamento", "")
        if not matricula:
            raise SourceError("uy.sucive", "Matrícula (plate) is required")
        return self._query(matricula.strip(), padron, departamento, audit=input.audit)

    def _query(self, matricula: str, padron: str, departamento: str, audit: bool = False) -> UySuciveResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("uy.sucive", "plate", matricula)

        with browser.page(SUCIVE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill matricula
                mat_input = page.query_selector(
                    '#matricula, input[name*="matricula"], '
                    'input[id*="matricula"], input[type="text"]'
                )
                if not mat_input:
                    raise SourceError("uy.sucive", "Could not find matrícula input field")

                mat_input.fill(matricula.upper())
                logger.info("Filled matrícula: %s", matricula)

                # Fill padron if provided
                if padron:
                    padron_input = page.query_selector(
                        '#padron, input[name*="padron"]'
                    )
                    if padron_input:
                        padron_input.fill(padron)

                # Fill departamento if provided
                if departamento:
                    dep_select = page.query_selector(
                        '#departamento, select[name*="departamento"]'
                    )
                    if dep_select:
                        page.select_option(
                            '#departamento, select[name*="departamento"]',
                            label=departamento,
                        )

                # Solve reCAPTCHA Enterprise if present
                from openquery.core.captcha_middleware import solve_page_captchas
                solve_page_captchas(page)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit — exact ID: #id1 (Wicket framework)
                submit = page.query_selector(
                    '#id1, button[name*="buscarLink"], '
                    'button:has-text("Consulta")'
                )
                if submit:
                    submit.click()
                else:
                    mat_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, matricula, padron, departamento)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("uy.sucive", f"Query failed: {e}") from e

    def _parse_result(self, page, matricula: str, padron: str, departamento: str) -> UySuciveResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = UySuciveResult(
            queried_at=datetime.now(),
            matricula=matricula,
            padron=padron,
            departamento=departamento,
        )

        field_map = {
            "marca": "marca",
            "modelo": "modelo",
            "año": "anio",
            "valor": "valor_patente",
            "deuda": "deuda",
            "estado": "estado",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and (":" in stripped or "\t" in stripped):
                    sep = ":" if ":" in stripped else "\t"
                    value = stripped.split(sep, 1)[1].strip()
                    setattr(result, field, value)
                    break

        return result
