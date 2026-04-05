"""Mi Casa Ya source — Colombian housing subsidy program lookup.

Queries the Ministerio de Vivienda for housing subsidies (Mi Casa Ya)
by cédula number.

Flow:
1. Navigate to Minvivienda consultation page
2. Enter cédula number
3. Submit and parse subsidy records from result table

Source: https://www.minvivienda.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.mi_casa_ya import MiCasaYaResult, SubsidioVivienda
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MINVIVIENDA_URL = "https://www.minvivienda.gov.co/"


@register
class MiCasaYaSource(BaseSource):
    """Query Colombian housing subsidy program (Mi Casa Ya)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.mi_casa_ya",
            display_name="Mi Casa Ya \u2014 Subsidios de Vivienda",
            description="Colombian housing subsidy program lookup (Mi Casa Ya)",
            country="CO",
            url=MINVIVIENDA_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        raise SourceError(
            "co.mi_casa_ya",
            "Source deprecated: Mi Casa Ya subsidy lookup portal is no longer available — micasaya.gov.co DNS dead and minvivienda.gov.co removed the query form since 2026-04",
        )

    def _query(self, cedula: str, audit: bool = False) -> MiCasaYaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.mi_casa_ya", "cedula", cedula)

        with browser.page(MINVIVIENDA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                # Wait for form to load
                page.wait_for_selector(
                    'input[type="text"], input[type="number"]',
                    timeout=15000,
                )
                page.wait_for_timeout(2000)

                # Fill cedula number
                doc_input = page.query_selector(
                    'input[type="text"][id*="cedula"], '
                    'input[type="text"][id*="numero"], '
                    'input[type="text"][id*="documento"], '
                    'input[type="text"][name*="cedula"], '
                    'input[type="text"]'
                )
                if not doc_input:
                    raise SourceError("co.mi_casa_ya", "Could not find cedula input field")

                doc_input.fill(cedula)
                logger.info("Filled cedula: %s", cedula)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'a[id*="consultar"], a[id*="buscar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    doc_input.press("Enter")

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
                raise SourceError("co.mi_casa_ya", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> MiCasaYaResult:
        """Parse the Minvivienda result page for housing subsidy info."""
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        # Check for no records
        no_records = any(phrase in body_lower for phrase in [
            "no se encontr",
            "no aparece",
            "no registra",
            "sin resultados",
            "no tiene subsidio",
            "no ha sido beneficiario",
        ])

        nombre = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if any(label in lower for label in ["nombre", "beneficiario"]):
                parts = stripped.split(":")
                if len(parts) > 1 and not nombre:
                    nombre = parts[1].strip()

        # Parse subsidies from table rows
        subsidios: list[SubsidioVivienda] = []
        rows = page.query_selector_all(
            "table tbody tr, .resultado-row, .subsidio-item"
        )

        for row in rows:
            text = row.inner_text()
            if not text.strip():
                continue
            cells = text.split("\t")
            # Try to extract columns: programa, estado, valor, fecha, proyecto, municipio
            if len(cells) >= 2:
                subsidio = SubsidioVivienda(
                    programa=cells[0].strip() if cells else "",
                    estado=cells[1].strip() if len(cells) > 1 else "",
                    valor=cells[2].strip() if len(cells) > 2 else "",
                    fecha=cells[3].strip() if len(cells) > 3 else "",
                    proyecto=cells[4].strip() if len(cells) > 4 else "",
                    municipio=cells[5].strip() if len(cells) > 5 else "",
                )
                subsidios.append(subsidio)

        # Also try extracting from key-value lines if no table
        if not subsidios and not no_records:
            programa = ""
            estado_sub = ""
            valor = ""
            fecha = ""
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if "programa" in lower and ":" in stripped:
                    programa = stripped.split(":", 1)[1].strip()
                elif "estado" in lower and ":" in stripped:
                    estado_sub = stripped.split(":", 1)[1].strip()
                elif "valor" in lower and ":" in stripped:
                    valor = stripped.split(":", 1)[1].strip()
                elif "fecha" in lower and ":" in stripped:
                    fecha = stripped.split(":", 1)[1].strip()
            if programa or estado_sub:
                subsidios.append(SubsidioVivienda(
                    programa=programa,
                    estado=estado_sub,
                    valor=valor,
                    fecha=fecha,
                ))

        tiene_subsidio = len(subsidios) > 0 and not no_records

        mensaje = ""
        if no_records:
            mensaje = "No se encontraron subsidios de vivienda"
        elif tiene_subsidio:
            mensaje = f"Se encontraron {len(subsidios)} subsidio(s) de vivienda"

        return MiCasaYaResult(
            queried_at=datetime.now(),
            cedula=cedula,
            nombre=nombre,
            tiene_subsidio=tiene_subsidio,
            subsidios=subsidios,
            mensaje=mensaje,
        )
