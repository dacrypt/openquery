"""Consulta de Procesos source — Colombian judicial processes lookup.

Queries the Rama Judicial for judicial processes by document number,
NIT, or name.

Flow:
1. Navigate to Rama Judicial process consultation page
2. Enter document number or name
3. Parse process records from result table

Source: https://consultaprocesos.ramajudicial.gov.co/Procesos/NombreRazonSocial
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.consulta_procesos import ConsultaProcesosResult, ProcesoJudicial
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

RAMA_JUDICIAL_URL = (
    "https://consultaprocesos.ramajudicial.gov.co/Procesos/NombreRazonSocial"
)


@register
class ConsultaProcesosSource(BaseSource):
    """Query Colombian judicial processes (Rama Judicial)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.consulta_procesos",
            display_name="Rama Judicial \u2014 Consulta de Procesos",
            description="Colombian judicial processes lookup from Rama Judicial",
            country="CO",
            url=RAMA_JUDICIAL_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.NIT, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.document_number.strip()
        name = input.extra.get("name", "").strip()
        if not search_term and not name:
            raise SourceError(
                "co.consulta_procesos",
                "Provide a document number or name (extra.name)",
            )

        query_term = search_term if search_term else name
        tipo = {
            DocumentType.CEDULA: "cedula",
            DocumentType.NIT: "nit",
        }.get(input.document_type, "nombre")

        return self._query(query_term, tipo, audit=input.audit)

    def _query(self, query: str, tipo: str, audit: bool = False) -> ConsultaProcesosResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.consulta_procesos", tipo, query)

        with browser.page(RAMA_JUDICIAL_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                # Wait for the SPA form — ARIA textboxes rendered by Angular/React
                search_input = page.get_by_role(
                    "textbox", name="Nombre"
                )
                search_input.wait_for(state="visible", timeout=15000)
                page.wait_for_timeout(2000)

                # Fill "Nombre(s) Apellido o Razón Social" textbox
                search_input.fill(query)
                logger.info("Searching Rama Judicial for: %s (type=%s)", query, tipo)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit — target the elevated submit button, not the nav icon
                submit_btn = page.locator(
                    'button.v-btn--has-bg[aria-label*="onsultar"]'
                )
                submit_btn.click()

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, query)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.consulta_procesos", f"Query failed: {e}") from e

    def _parse_result(self, page, query: str) -> ConsultaProcesosResult:
        """Parse the Rama Judicial result page for judicial process records."""
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        no_records = any(phrase in body_lower for phrase in [
            "no se encontr",
            "sin resultados",
            "no hay resultados",
            "0 resultados",
            "no registra procesos",
        ])

        nombre = ""
        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if any(label in lower for label in ["nombre", "razon social", "raz\u00f3n social"]):
                parts = stripped.split(":")
                if len(parts) > 1 and not nombre:
                    nombre = parts[1].strip()

        # Parse process records from table rows
        procesos: list[ProcesoJudicial] = []
        rows = page.query_selector_all(
            "table tbody tr, .proceso-row, .resultado-item"
        )

        for row in rows:
            text = row.inner_text()
            if not text.strip():
                continue
            cells = text.split("\t")
            # Try to extract: radicacion, despacho, tipo, clase, sujetos, fecha_radicacion,
            # fecha_ultima_actuacion, ultima_actuacion
            if len(cells) >= 2:
                proceso = ProcesoJudicial(
                    radicacion=cells[0].strip() if cells else "",
                    despacho=cells[1].strip() if len(cells) > 1 else "",
                    tipo_proceso=cells[2].strip() if len(cells) > 2 else "",
                    clase=cells[3].strip() if len(cells) > 3 else "",
                    sujetos=cells[4].strip() if len(cells) > 4 else "",
                    fecha_radicacion=cells[5].strip() if len(cells) > 5 else "",
                    fecha_ultima_actuacion=cells[6].strip() if len(cells) > 6 else "",
                    ultima_actuacion=cells[7].strip() if len(cells) > 7 else "",
                )
                procesos.append(proceso)

        # Fallback: try extracting from key-value lines
        if not procesos and not no_records:
            radicacion = ""
            despacho = ""
            tipo_proceso = ""
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if any(k in lower for k in ["radicaci", "radicado", "n\u00famero de proceso"]):
                    parts = stripped.split(":")
                    if len(parts) > 1:
                        radicacion = parts[1].strip()
                elif "despacho" in lower and ":" in stripped:
                    despacho = stripped.split(":", 1)[1].strip()
                elif any(k in lower for k in ["tipo proceso", "tipo de proceso"]):
                    parts = stripped.split(":")
                    if len(parts) > 1:
                        tipo_proceso = parts[1].strip()
            if radicacion or despacho:
                procesos.append(ProcesoJudicial(
                    radicacion=radicacion,
                    despacho=despacho,
                    tipo_proceso=tipo_proceso,
                ))

        total_procesos = len(procesos)

        mensaje = ""
        if no_records:
            mensaje = "No se encontraron procesos judiciales"
        elif total_procesos > 0:
            mensaje = f"Se encontraron {total_procesos} proceso(s) judicial(es)"

        return ConsultaProcesosResult(
            queried_at=datetime.now(),
            documento=query,
            nombre=nombre,
            total_procesos=total_procesos,
            procesos=procesos,
            mensaje=mensaje,
        )
