"""Garantías Mobiliarias source — Colombian movable collateral registry.

Queries the Confecámaras Garantías Mobiliarias registry for
movable collateral guarantees by cédula.

Flow:
1. Navigate to Garantías Mobiliarias consultation page
2. Enter cédula number
3. Parse results for guarantee entries

Source: https://www.garantiasmobiliarias.com.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.garantias_mobiliarias import GarantiaEntry, GarantiasMobiliariasResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

GARANTIAS_URL = "https://www.garantiasmobiliarias.com.co/"


@register
class GarantiasMobiliariasSource(BaseSource):
    """Query Colombian movable collateral guarantees registry (Confecámaras)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.garantias_mobiliarias",
            display_name="Garantías Mobiliarias — Registro de Garantías",
            description="Colombian movable collateral guarantees registry (Confecámaras)",
            country="CO",
            url=GARANTIAS_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError("co.garantias_mobiliarias", f"Only cedula supported, got: {input.document_type}")
        return self._query(input.document_number, audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> GarantiasMobiliariasResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.garantias_mobiliarias", "cedula", cedula)

        with browser.page(GARANTIAS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill cedula
                cedula_input = page.query_selector(
                    'input[type="text"][id*="documento"], '
                    'input[type="text"][id*="cedula"], '
                    'input[type="text"][id*="numero"], '
                    'input[type="text"]'
                )
                if not cedula_input:
                    raise SourceError("co.garantias_mobiliarias", "Could not find document input field")

                cedula_input.fill(cedula)
                logger.info("Searching Garantías Mobiliarias for: %s", cedula)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    cedula_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cedula)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.garantias_mobiliarias", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> GarantiasMobiliariasResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = GarantiasMobiliariasResult(
            queried_at=datetime.now(),
            documento=cedula,
        )

        # Extract name
        for line in body_text.split("\n"):
            stripped = line.strip()
            if "nombre" in stripped.lower() and ":" in stripped:
                result.nombre = stripped.split(":", 1)[1].strip()
                break

        # Try to extract guarantee rows from tables
        rows = page.query_selector_all("table tr, .resultado, .item-resultado")

        garantias = []
        for row in rows:
            text = row.inner_text()
            if not text.strip():
                continue
            cells = text.split("\t")
            if len(cells) >= 3:
                garantias.append(GarantiaEntry(
                    numero_registro=cells[0].strip() if cells else "",
                    tipo_garantia=cells[1].strip() if len(cells) > 1 else "",
                    deudor=cells[2].strip() if len(cells) > 2 else "",
                    acreedor=cells[3].strip() if len(cells) > 3 else "",
                    descripcion_bien=cells[4].strip() if len(cells) > 4 else "",
                    fecha_inscripcion=cells[5].strip() if len(cells) > 5 else "",
                    estado=cells[6].strip() if len(cells) > 6 else "",
                ))

        result.garantias = garantias
        result.total_garantias = len(garantias)
        result.tiene_garantias = len(garantias) > 0
        result.mensaje = f"Garantías Mobiliarias {cedula}: {len(garantias)} garantía(s) encontrada(s)"

        return result
