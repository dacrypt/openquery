"""SEP source — Mexico professional certification (cédula profesional) lookup.

Queries Mexico's SEP for professional license status by name.

Flow:
1. Navigate to the SEP cédula profesional portal
2. Enter professional name
3. Submit and parse license details

Source: https://www.cedulaprofesional.sep.gob.mx/cedula/presidencia/indexAvanzada.action
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.sep import SepResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SEP_URL = "https://www.cedulaprofesional.sep.gob.mx/cedula/presidencia/indexAvanzada.action"


@register
class SepSource(BaseSource):
    """Query Mexico's SEP professional certification portal."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.sep",
            display_name="SEP — Cédula Profesional",
            description="Mexico professional license: cédula profesional status and institution by name",  # noqa: E501
            country="MX",
            url=SEP_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("mx.sep", f"Unsupported input type: {input.document_type}")

        nombre = input.extra.get("nombre", "").strip()
        if not nombre:
            raise SourceError("mx.sep", "Must provide extra['nombre'] (professional name)")

        return self._query(nombre=nombre, audit=input.audit)

    def _query(self, nombre: str, audit: bool = False) -> SepResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("mx.sep", "nombre", nombre)

        with browser.page(SEP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                name_input = page.query_selector(
                    'input[id*="nombre"], input[name*="nombre"], '
                    'input[placeholder*="nombre" i], input[type="text"]'
                )
                if name_input:
                    name_input.fill(nombre)
                    logger.info("Filled nombre: %s", nombre)

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

                page.wait_for_timeout(4000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, nombre)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("mx.sep", f"Query failed: {e}") from e

    def _parse_result(self, page, nombre: str) -> SepResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SepResult(queried_at=datetime.now(), nombre=nombre)
        details: dict = {}

        rows = page.query_selector_all("table tr, .result tr")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip()
                value = (cells[1].inner_text() or "").strip()
                if label and value:
                    details[label] = value
                    label_lower = label.lower()
                    if "c\u00e9dula" in label_lower or "numero" in label_lower or "n\u00famero" in label_lower:  # noqa: E501
                        result.cedula_number = value
                    elif "instituci" in label_lower or "escuela" in label_lower:
                        result.institution = value
                    elif "carrera" in label_lower or "titulo" in label_lower or "t\u00edtulo" in label_lower:  # noqa: E501
                        result.degree = value

        if details:
            result.details = details

        # Fallback: body text scan
        if not result.cedula_number:
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if ("c\u00e9dula" in lower or "cedula" in lower) and ":" in stripped:
                    result.cedula_number = stripped.split(":", 1)[1].strip()
                elif "instituci" in lower and ":" in stripped and not result.institution:
                    result.institution = stripped.split(":", 1)[1].strip()
                elif ("carrera" in lower or "titulo" in lower) and ":" in stripped and not result.degree:  # noqa: E501
                    result.degree = stripped.split(":", 1)[1].strip()

        return result
