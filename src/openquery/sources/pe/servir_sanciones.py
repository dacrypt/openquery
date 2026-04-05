"""SERVIR Sanciones source — Peruvian public servant sanctions.

Queries SERVIR for sanctions imposed on public servants.

Flow:
1. Navigate to sanciones.gob.pe
2. Enter name or DNI
3. Submit search
4. Parse result table rows
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.servir_sanciones import SancionServidor, ServirSancionesResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SERVIR_URL = "https://www.sanciones.gob.pe/"


@register
class ServirSancionesSource(BaseSource):
    """Query Peruvian public servant sanctions (SERVIR)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.servir_sanciones",
            display_name="SERVIR — Sanciones a Servidores Publicos",
            description="Peruvian public servant sanctions: disciplinary actions and disqualifications",
            country="PE",
            url=SERVIR_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        raise SourceError("pe.servir_sanciones", "Source deprecated: site unreachable since 2026-04")
        nombre = input.extra.get("nombre", "")
        dni = input.extra.get("dni", "")
        if not nombre and not dni:
            raise SourceError(
                "pe.servir_sanciones",
                "Must provide extra.nombre or extra.dni",
            )
        return self._query(nombre=nombre, dni=dni, audit=input.audit)

    def _query(
        self,
        nombre: str = "",
        dni: str = "",
        audit: bool = False,
    ) -> ServirSancionesResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector(
                "pe.servir_sanciones", "custom", nombre or dni
            )

        with browser.page(SERVIR_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_selector(
                    "input[type='text'], #txtBusqueda, #txtNombre",
                    timeout=15000,
                )
                page.wait_for_timeout(2000)

                search_value = nombre or dni
                search_input = page.query_selector(
                    "#txtBusqueda, #txtNombre, #txtDni, "
                    "input[name*='busqueda'], input[name*='nombre'], "
                    "input[type='text']"
                )
                if search_input:
                    search_input.fill(search_value)
                    logger.info("Filled search: %s", search_value)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    "#btnBuscar, input[value='Buscar'], "
                    "button:has-text('Buscar'), button:has-text('Consultar')"
                )
                if submit:
                    submit.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector(
                    "table, .resultado, #divResultado, .list-group",
                    timeout=15000,
                )

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page)

                if collector:
                    result.audit = collector.generate_pdf(
                        page, result.model_dump_json()
                    )

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError(
                    "pe.servir_sanciones", f"Query failed: {e}"
                ) from e

    def _parse_result(self, page) -> ServirSancionesResult:
        """Parse the SERVIR sanciones result page."""
        from datetime import datetime

        body_text = page.inner_text("body")
        result = ServirSancionesResult(queried_at=datetime.now())

        rows = page.query_selector_all("table tbody tr, table tr")
        sanciones: list[SancionServidor] = []

        for row in rows:
            cells = row.query_selector_all("td")
            if not cells or len(cells) < 3:
                continue
            values = [(c.inner_text() or "").strip() for c in cells]
            sancion = SancionServidor(
                nombre=values[0] if len(values) > 0 else "",
                entidad=values[1] if len(values) > 1 else "",
                tipo_sancion=values[2] if len(values) > 2 else "",
                fecha=values[3] if len(values) > 3 else "",
                duracion=values[4] if len(values) > 4 else "",
                estado=values[5] if len(values) > 5 else "",
            )
            sanciones.append(sancion)

        result.sanciones = sanciones
        result.total_sanciones = len(sanciones)

        # Fallback: extract count from text
        if not sanciones:
            m = re.search(
                r"(\d+)\s*(?:resultado|registro|sanci[oó]n)", body_text, re.IGNORECASE
            )
            if m:
                result.total_sanciones = int(m.group(1))

        return result
