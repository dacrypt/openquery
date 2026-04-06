"""Paraguay TSJE source — electoral registry.

Queries the Tribunal Superior de Justicia Electoral (TSJE) for
voter status and polling location by CI and date of birth.

Source: https://padron.tsje.gov.py/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.py.tsje import PyTsjeResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

TSJE_URL = "https://padron.tsje.gov.py/"


@register
class PyTsjeSource(BaseSource):
    """Query Paraguayan electoral registry (TSJE) by CI and date of birth."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="py.tsje",
            display_name="TSJE — Padrón Electoral",
            description="Paraguay electoral registry: voter status, polling location (TSJE)",
            country="PY",
            url=TSJE_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        ci = input.document_number or input.extra.get("ci", "")
        fecha_nacimiento = input.extra.get("fecha_nacimiento", "")
        if not ci:
            raise SourceError("py.tsje", "CI (cédula) is required")
        return self._query(ci.strip(), fecha_nacimiento.strip(), audit=input.audit)

    def _query(self, ci: str, fecha_nacimiento: str, audit: bool = False) -> PyTsjeResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("py.tsje", "cedula", ci)

        with browser.page(TSJE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                ci_input = page.query_selector(
                    'input[name*="cedula"], input[id*="cedula"], '
                    'input[name*="ci"], input[id*="ci"], '
                    'input[type="text"]'
                )
                if not ci_input:
                    raise SourceError("py.tsje", "Could not find CI input field")

                ci_input.fill(ci)
                logger.info("Filled CI: %s", ci)

                if fecha_nacimiento:
                    fecha_input = page.query_selector(
                        'input[name*="fecha"], input[id*="fecha"], '
                        'input[name*="nacimiento"], input[type="date"]'
                    )
                    if fecha_input:
                        fecha_input.fill(fecha_nacimiento)
                        logger.info("Filled fecha_nacimiento: %s", fecha_nacimiento)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar")'
                )
                if submit:
                    submit.click()
                else:
                    ci_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, ci)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("py.tsje", f"Query failed: {e}") from e

    def _parse_result(self, page, ci: str) -> PyTsjeResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = PyTsjeResult(queried_at=datetime.now(), ci=ci)

        field_map = {
            "nombre": "nombre",
            "lugar de votacion": "lugar_votacion",
            "local": "lugar_votacion",
            "mesa": "mesa",
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
