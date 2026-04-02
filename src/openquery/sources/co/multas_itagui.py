"""Multas Itagüí source — Itagüí traffic fines via QITS portal.

Queries Itagüí's Secretaría de Movilidad via the QITS (Java/PrimeFaces) portal.

Flow:
1. Navigate to QITS main menu
2. Click "Consultar infracciones" link via dispatch_event
3. Select document type, fill number
4. Click "Buscar" button and parse datatable results

No CAPTCHA required.

Source: https://comp.transitoitagui.gov.co/portal/qits/
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.multas_transito import (
    ComparendoLocal,
    MultasTransitoLocalResult,
)
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

QITS_URL = (
    "https://comp.transitoitagui.gov.co/portal/qits/"
    "menuPrincipalPortal?execution=e1s1"
)

# QITS document type codes
QITS_DOC_TYPES = {
    "CC": "2",   # Cedula Ciudadania
    "CE": "4",   # Cedula Extranjeria
    "NIT": "3",
    "PA": "6",   # Pasaporte
    "TI": "5",   # Tarjeta Identidad
    "RC": "21",  # Registro Civil
    "PPT": "9",  # Permiso por Protección Temporal
}


@register
class MultasItaguiSource(BaseSource):
    """Query Itagüí traffic fines from the QITS portal."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.multas_itagui",
            display_name="Tránsito Itagüí — Multas y Comparendos",
            description=(
                "Itagüí traffic fines and violations from the "
                "Secretaría de Movilidad (QITS portal)"
            ),
            country="CO",
            url="https://comp.transitoitagui.gov.co/portal/qits/",
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError(
                "co.multas_itagui",
                f"Unsupported input type: {input.document_type}. Use CEDULA.",
            )
        return self._query(input.document_number, audit=input.audit)

    def _query(self, doc_number: str, audit: bool = False) -> MultasTransitoLocalResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("co.multas_itagui", "cedula", doc_number)

        with browser.page(QITS_URL, wait_until="load") as page:
            try:
                if collector:
                    collector.attach(page)

                # Wait for page to fully load
                page.wait_for_timeout(3000)

                # Navigate to "Consultar infracciones" via DOM click
                nav_link = page.locator("#j_idt76")
                nav_link.dispatch_event("click")
                logger.info("Navigated to Consultar infracciones")
                page.wait_for_timeout(3000)

                # Wait for form to appear
                page.wait_for_selector(
                    "#formInfracciones\\:selectTipoIdentificacion",
                    timeout=10000,
                )

                # Select document type (CC = 2)
                page.select_option(
                    "#formInfracciones\\:selectTipoIdentificacion",
                    QITS_DOC_TYPES.get("CC", "2"),
                )
                # Trigger onchange via the select element
                page.locator(
                    "#formInfracciones\\:selectTipoIdentificacion"
                ).dispatch_event("change")
                page.wait_for_timeout(2000)

                # Fill document number
                page.fill(
                    "#formInfracciones\\:textNroIdentificacion",
                    doc_number,
                )
                logger.info("Filled document: %s", doc_number)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Click Buscar button
                page.locator("#formInfracciones\\:btnBuscar").dispatch_event("click")
                logger.info("Submitted search")
                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                return self._parse_results(page, doc_number, collector)

            except SourceError:
                raise
            except Exception as e:
                raise SourceError(
                    "co.multas_itagui", f"Query failed: {e}"
                ) from e

    def _parse_results(
        self, page, doc_number: str, collector
    ) -> MultasTransitoLocalResult:
        """Parse QITS datatable results."""
        body_text = page.inner_text("body")

        # Check for "Total registros encontrados: N"
        total_match = re.search(
            r"Total registros encontrados:\s*(\d+)", body_text
        )
        total_found = int(total_match.group(1)) if total_match else 0

        if total_found == 0:
            return MultasTransitoLocalResult(
                queried_at=datetime.now(),
                documento=doc_number,
                ciudad="Itagüí",
                mensaje="No registra infracciones en Itagüí",
            )

        # Parse datatable rows
        comparendos: list[ComparendoLocal] = []
        total_deuda = 0.0

        rows = page.query_selector_all(".ui-datatable-data tr")
        for row in rows:
            cells = row.query_selector_all("td")
            if len(cells) >= 6:
                cell_texts = [
                    (cells[i].inner_text() or "").strip() for i in range(6)
                ]
                nro_comparendo = cell_texts[0]
                nro_resolucion = cell_texts[1]
                fecha = cell_texts[2]
                estado = cell_texts[3]
                # cell_texts[4] = "Ver" (link to detail)
                valor_str = cell_texts[5]

                valor = 0.0
                clean_val = re.sub(r"[^\d]", "", valor_str)
                if clean_val:
                    valor = float(clean_val)

                comp = ComparendoLocal(
                    numero=nro_comparendo,
                    tipo="Comparendo" if not nro_resolucion else "Resolución",
                    fecha=fecha,
                    estado=estado,
                    saldo=valor,
                    total=valor,
                )
                comparendos.append(comp)
                if estado.lower() != "pagado":
                    total_deuda += valor

        result = MultasTransitoLocalResult(
            queried_at=datetime.now(),
            documento=doc_number,
            ciudad="Itagüí",
            total_comparendos=len(comparendos),
            total_deuda=total_deuda,
            comparendos=comparendos,
            mensaje=f"Se encontraron {len(comparendos)} infracción(es) en Itagüí",
        )

        if collector:
            result_json = result.model_dump_json()
            result.audit = collector.generate_pdf(page, result_json)

        logger.info(
            "Itagüí results — %d infracciones, deuda pendiente=$%.0f",
            result.total_comparendos,
            result.total_deuda,
        )
        return result
