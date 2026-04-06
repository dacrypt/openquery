"""Comparendos de Tránsito source — Colombian traffic violations detailed lookup.

Queries SIMIT for individual comparendo (traffic violation) records,
providing more detail than the summary-level SIMIT source.

Flow:
1. Navigate to SIMIT consultation page
2. Enter cédula or plate number
3. Click through to detailed comparendos view
4. Parse individual comparendo records from table

Source: https://www.fcm.org.co/simit/
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.comparendos_transito import (
    Comparendo,
    ComparendosTransitoResult,
)
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SIMIT_COMPARENDOS_URL = "https://www.fcm.org.co/simit/#/estado-cuenta"


@register
class ComparendosTransitoSource(BaseSource):
    """Query Colombian traffic violations (comparendos) from SIMIT."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.comparendos_transito",
            display_name="SIMIT — Comparendos de Tránsito",
            description="Colombian traffic violations (comparendos) detailed lookup from SIMIT",
            country="CO",
            url=SIMIT_COMPARENDOS_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in (DocumentType.CEDULA, DocumentType.PLATE):
            raise SourceError(
                "co.comparendos_transito",
                f"Unsupported input type: {input.document_type}",
            )

        return self._query(input.document_number, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> ComparendosTransitoResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("co.comparendos_transito", "cedula/placa", search_term)

        with browser.page(SIMIT_COMPARENDOS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                # Wait for the Angular SPA to render
                logger.info("Waiting for SIMIT search form...")
                input_locator = page.get_by_label("Número de identificación o placa del vehículo")
                input_locator.wait_for(state="visible", timeout=15000)

                # Fill search term
                input_locator.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Wait for anti-bot JS
                page.wait_for_timeout(2000)

                # Click submit
                submit_locator = page.get_by_role("button", name="Realizar consulta")
                submit_locator.click()
                logger.info("Clicked submit button")

                # Wait for results
                page.wait_for_selector(
                    'strong, [class*="resumen"], [class*="result"], '
                    'h3:has-text("No tienes"), table',
                    timeout=20000,
                )
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "summary_result")

                # Try to click "Ver detalle" or "Ver comparendos" for details
                detail_btn = page.query_selector(
                    'button:has-text("Ver detalle"), '
                    'button:has-text("Ver comparendos"), '
                    'a:has-text("Ver detalle"), '
                    'a:has-text("Detalle comparendos")'
                )
                if detail_btn:
                    detail_btn.click()
                    page.wait_for_timeout(3000)
                    logger.info("Clicked detail button")

                    if collector:
                        collector.screenshot(page, "detail_result")

                result = self._parse_result(page, search_term)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.comparendos_transito", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> ComparendosTransitoResult:
        """Parse individual comparendo records from the SIMIT detail page."""
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        nombre = ""
        total_deuda = 0.0

        # Check for paz y salvo
        paz_salvo = (
            page.query_selector('img[alt*="Paz y Salvo"]') is not None
            or "no tienes comparendos ni multas" in body_lower
        )

        # Extract name
        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nombre" in lower and ":" in stripped and not nombre:
                nombre = stripped.split(":", 1)[1].strip()

        # Extract total amount
        m = re.search(r"Total:\s*\$\s*([\d.,]+)", body_text)
        if m:
            amount_str = m.group(1).replace(".", "").replace(",", ".")
            try:
                total_deuda = float(amount_str)
            except ValueError:
                total_deuda = 0.0

        # Parse individual comparendos from table rows
        comparendos: list[Comparendo] = []
        rows = page.query_selector_all("table tbody tr")

        for row in rows:
            cells = row.query_selector_all("td")
            if len(cells) >= 4:
                comparendo = Comparendo(
                    numero=(cells[0].inner_text() or "").strip(),
                    fecha=(cells[1].inner_text() or "").strip(),
                    infraccion=(cells[2].inner_text() or "").strip(),
                    codigo_infraccion=(cells[3].inner_text() or "").strip()
                    if len(cells) > 3
                    else "",
                    valor=(cells[4].inner_text() or "").strip() if len(cells) > 4 else "",
                    estado=(cells[5].inner_text() or "").strip() if len(cells) > 5 else "",
                    secretaria_transito=(cells[6].inner_text() or "").strip()
                    if len(cells) > 6
                    else "",
                    placa=(cells[7].inner_text() or "").strip() if len(cells) > 7 else "",
                )
                comparendos.append(comparendo)

        # Fallback: try parsing from line-based format
        if not comparendos and not paz_salvo:
            current: dict[str, str] = {}
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if "comparendo" in lower and ":" in stripped:
                    if current.get("numero"):
                        comparendos.append(Comparendo(**current))
                        current = {}
                    current["numero"] = stripped.split(":", 1)[1].strip()
                elif "fecha" in lower and ":" in stripped and "numero" in current:
                    current["fecha"] = stripped.split(":", 1)[1].strip()
                elif "infracci" in lower and ":" in stripped:
                    current["infraccion"] = stripped.split(":", 1)[1].strip()
                elif "valor" in lower and ":" in stripped:
                    current["valor"] = stripped.split(":", 1)[1].strip()
                elif "estado" in lower and ":" in stripped:
                    current["estado"] = stripped.split(":", 1)[1].strip()
            if current.get("numero"):
                comparendos.append(Comparendo(**current))

        total_comparendos = len(comparendos)

        mensaje = ""
        if paz_salvo:
            mensaje = "Paz y salvo — no registra comparendos"
        elif total_comparendos > 0:
            mensaje = f"Se encontraron {total_comparendos} comparendo(s)"
        else:
            mensaje = "Consulta realizada"

        return ComparendosTransitoResult(
            queried_at=datetime.now(),
            documento=search_term,
            nombre=nombre,
            total_comparendos=total_comparendos,
            total_deuda=total_deuda,
            comparendos=comparendos,
            mensaje=mensaje,
        )
