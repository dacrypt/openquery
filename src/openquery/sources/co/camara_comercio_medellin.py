"""Cámara de Comercio de Medellín source — business registry for Antioquia.

Queries the Cámara de Comercio de Medellín para Antioquia for
business registration records (expedientes).

Flow:
1. Navigate to the expediente consultation page
2. Enter NIT or company name
3. Submit and parse result table

Source: https://tramites.camaramedellin.com.co/tramites-virtuales/consulta-de-expedientes
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.camara_comercio_medellin import (
    CamaraComercioMedellinResult,
    ExpedienteMedellin,
)
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CAMARA_URL = "https://tramites.camaramedellin.com.co/tramites-virtuales/consulta-de-expedientes"


@register
class CamaraComercioMedellinSource(BaseSource):
    """Query Medellín Chamber of Commerce business registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.camara_comercio_medellin",
            display_name="Cámara Medellín — Consulta Expedientes",
            description="Business registry lookup from Cámara de Comercio de Medellín para Antioquia",
            country="CO",
            url=CAMARA_URL,
            supported_inputs=[DocumentType.NIT, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.document_number.strip()
        name = input.extra.get("name", "").strip()
        if not search_term and not name:
            raise SourceError("co.camara_comercio_medellin", "Provide a NIT or company name (extra.name)")

        query_term = search_term if search_term else name
        tipo = "nit" if input.document_type == DocumentType.NIT else "nombre"
        return self._query(query_term, tipo, audit=input.audit)

    def _query(self, query: str, tipo: str, audit: bool = False) -> CamaraComercioMedellinResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.camara_comercio_medellin", tipo, query)

        with browser.page(CAMARA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_selector('input[type="text"]', timeout=15000)
                page.wait_for_timeout(2000)

                # Fill search input
                search_input = page.query_selector(
                    'input[type="text"][id*="nit"], '
                    'input[type="text"][id*="buscar"], '
                    'input[type="text"][id*="razon"], '
                    'input[type="text"][name*="nit"], '
                    'input[type="text"][placeholder*="NIT"], '
                    'input[type="text"][placeholder*="razón"], '
                    'input[type="text"][placeholder*="buscar"], '
                    'input[type="search"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("co.camara_comercio_medellin", "Could not find search input field")

                search_input.fill(query)
                logger.info("Searching Cámara Medellín for: %s (type=%s)", query, tipo)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="buscar"], button[id*="consultar"], '
                    'a[id*="buscar"], a[id*="consultar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, query, tipo)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.camara_comercio_medellin", f"Query failed: {e}") from e

    def _parse_result(self, page, query: str, tipo: str) -> CamaraComercioMedellinResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        no_records = any(phrase in body_lower for phrase in [
            "no se encontr",
            "sin resultados",
            "no hay resultados",
            "0 resultados",
        ])

        # Parse table rows for expedientes
        expedientes = []
        table_rows = page.query_selector_all("table tr, .resultado, .result-item")
        for row in table_rows:
            cells = row.query_selector_all("td")
            if len(cells) >= 3:
                cell_texts = [c.inner_text().strip() for c in cells]
                expedientes.append(ExpedienteMedellin(
                    matricula=cell_texts[0] if cell_texts else "",
                    razon_social=cell_texts[1] if len(cell_texts) > 1 else "",
                    estado=cell_texts[2] if len(cell_texts) > 2 else "",
                    tipo=cell_texts[3] if len(cell_texts) > 3 else "",
                    fecha_matricula=cell_texts[4] if len(cell_texts) > 4 else "",
                ))

        if no_records:
            mensaje = "No se encontraron expedientes"
        elif expedientes:
            mensaje = f"Se encontraron {len(expedientes)} expediente(s)"
        else:
            # Try line-by-line extraction for non-table layouts
            for line in body_text.split("\n"):
                stripped = line.strip()
                if stripped and not stripped.startswith(("Buscar", "Consulta", "Inicio")):
                    lower = stripped.lower()
                    if any(kw in lower for kw in ["matrícula", "matricula", "expediente"]):
                        expedientes.append(ExpedienteMedellin(razon_social=stripped))

            mensaje = f"Se encontraron {len(expedientes)} expediente(s)" if expedientes else ""

        return CamaraComercioMedellinResult(
            queried_at=datetime.now(),
            query=query,
            tipo_busqueda=tipo,
            expedientes=expedientes,
            total_expedientes=len(expedientes),
            mensaje=mensaje,
        )
