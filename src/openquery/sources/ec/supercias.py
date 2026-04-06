"""Supercias source — Ecuador company registry lookup.

Queries Ecuador's Superintendencia de Companias for company information
by RUC or company name.

Flow:
1. Navigate to the Supercias consultation page
2. Enter RUC or company name
3. Submit and parse result

Source: https://appscvsgen.supercias.gob.ec/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ec.supercias import SuperciasResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUPERCIAS_URL = "https://appscvsgen.supercias.gob.ec/"


@register
class SuperciasSource(BaseSource):
    """Query Ecuador company registry from Superintendencia de Companias."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ec.supercias",
            display_name="Supercias — Superintendencia de Companias",
            description="Ecuador company registry search from Superintendencia de Companias",
            country="EC",
            url=SUPERCIAS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("ec.supercias", f"Unsupported input type: {input.document_type}")

        ruc = input.extra.get("ruc", "").strip()
        name = input.extra.get("name", "").strip()

        if not ruc and not name:
            raise SourceError("ec.supercias", "Must provide extra['ruc'] or extra['name']")

        return self._query(ruc=ruc, name=name, audit=input.audit)

    def _query(self, ruc: str = "", name: str = "", audit: bool = False) -> SuperciasResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None
        search_term = ruc or name
        tipo_busqueda = "ruc" if ruc else "nombre"

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ec.supercias", tipo_busqueda, search_term)

        with browser.page(SUPERCIAS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill search field
                if ruc:
                    ruc_input = page.query_selector(
                        'input[id*="ruc"], input[name*="ruc"], '
                        'input[id*="expediente"], input[type="text"]'
                    )
                    if ruc_input:
                        ruc_input.fill(ruc)
                else:
                    name_input = page.query_selector(
                        'input[id*="nombre"], input[id*="compania"], '
                        'input[name*="nombre"], input[type="text"]'
                    )
                    if name_input:
                        name_input.fill(name)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'button:has-text("Consultar"), button:has-text("Buscar")'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term, tipo_busqueda)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ec.supercias", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str, tipo_busqueda: str) -> SuperciasResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        razon_social = ""
        ruc = ""
        estado = ""
        fecha_constitucion = ""
        representante_legal = ""
        objeto_social = ""
        capital = ""
        direccion = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if ("raz" in lower and "social" in lower) and ":" in stripped:
                razon_social = stripped.split(":", 1)[1].strip()
            elif "ruc" in lower and ":" in stripped:
                ruc = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped:
                estado = stripped.split(":", 1)[1].strip()
            elif ("fecha" in lower and "constituci" in lower) and ":" in stripped:
                fecha_constitucion = stripped.split(":", 1)[1].strip()
            elif "representante" in lower and ":" in stripped:
                representante_legal = stripped.split(":", 1)[1].strip()
            elif "objeto" in lower and ":" in stripped:
                objeto_social = stripped.split(":", 1)[1].strip()
            elif "capital" in lower and ":" in stripped:
                capital = stripped.split(":", 1)[1].strip()
            elif ("direcci" in lower or "domicilio" in lower) and ":" in stripped:
                direccion = stripped.split(":", 1)[1].strip()

        return SuperciasResult(
            queried_at=datetime.now(),
            query=search_term,
            tipo_busqueda=tipo_busqueda,
            razon_social=razon_social,
            ruc=ruc,
            estado=estado,
            fecha_constitucion=fecha_constitucion,
            representante_legal=representante_legal,
            objeto_social=objeto_social,
            capital=capital,
            direccion=direccion,
        )
