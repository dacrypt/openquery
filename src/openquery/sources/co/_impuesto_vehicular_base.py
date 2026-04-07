"""Shared base for Colombian departmental vehicle tax sources.

All 15 departmental sources share the same query flow and parse logic.
Each concrete source provides only its URL, name, departamento, and input requirements.
"""

from __future__ import annotations

import logging
import re

from openquery.exceptions import SourceError
from openquery.models.co.impuesto_vehicular import ImpuestoVehicularResult, VigenciaPendiente
from openquery.sources.base import BaseSource, DocumentType, QueryInput

logger = logging.getLogger(__name__)


class ImpuestoVehicularBaseSource(BaseSource):
    """Abstract base for all Colombian departmental vehicle tax sources."""

    #: Override in subclass — the source name (e.g. "co.impuesto_vehicular_bogota")
    _source_name: str = ""
    #: Override in subclass — the portal URL
    _source_url: str = ""
    #: Override in subclass — departamento label for the result
    _departamento: str = ""
    #: Whether this source needs extra.documento in addition to placa
    _needs_documento: bool = False

    def __init__(self, timeout: float = 45.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def query(self, input: QueryInput) -> ImpuestoVehicularResult:
        """Query vehicle tax by plate (and optionally documento)."""
        if input.document_type != DocumentType.PLATE:
            raise SourceError(self._source_name, f"Unsupported input type: {input.document_type}")

        placa = input.document_number.upper().strip()
        documento = input.extra.get("documento", "").strip() if self._needs_documento else ""
        return self._query(placa, documento=documento, audit=input.audit)

    def _query(
        self, placa: str, documento: str = "", audit: bool = False
    ) -> ImpuestoVehicularResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector(self._source_name, "placa", placa)

        with browser.page(self._source_url, wait_until="networkidle") as page:
            try:
                if collector:
                    collector.attach(page)

                logger.info("Searching %s vehicle tax for placa=%s", self._departamento, placa)

                # Fill plate field
                placa_sel = (
                    "input[name*='placa' i], input[id*='placa' i], "
                    "input[placeholder*='placa' i], input[name*='plate' i]"
                )
                placa_input = page.locator(placa_sel).first
                placa_input.wait_for(state="visible", timeout=15000)
                placa_input.fill(placa)

                # Fill documento if needed
                if self._needs_documento and documento:
                    doc_sel = (
                        "input[name*='documento' i], input[id*='documento' i], "
                        "input[placeholder*='documento' i], input[name*='cedula' i]"
                    )
                    doc_input = page.locator(doc_sel).first
                    if doc_input.count():
                        doc_input.fill(documento)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_sel = (
                    "button[type='submit'], input[type='submit'], "
                    "button:has-text('Consultar'), button:has-text('Buscar'), "
                    "button:has-text('Consulta')"
                )
                page.locator(submit_sel).first.click()
                page.wait_for_load_state("networkidle", timeout=25000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, placa)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError(self._source_name, f"Query failed: {e}") from e

    def _parse_result(self, page, placa: str) -> ImpuestoVehicularResult:
        """Parse vehicle tax result from page body and table rows."""
        body = page.inner_text("body")

        vigencias: list[VigenciaPendiente] = []
        details: dict[str, str] = {}

        # Extract vigencias from table rows (year + value columns)
        rows = page.query_selector_all("tr")
        for row in rows:
            cells = row.query_selector_all("td")
            if len(cells) >= 2:
                key = cells[0].inner_text().strip()
                val = cells[1].inner_text().strip()
                status = cells[2].inner_text().strip() if len(cells) >= 3 else ""
                if re.match(r"^\d{4}$", key):
                    vigencias.append(VigenciaPendiente(year=key, value=val, status=status))
                elif key:
                    details[key] = val

        # Extract vehicle characteristics from body text
        marca = _extract(body, r"[Mm]arca[:\s]+([A-Za-z0-9]+)")
        modelo = _extract(body, r"[Mm]odelo[:\s]+(\d{4})")
        cilindraje = _extract(body, r"[Cc]ilindraje[:\s]+([\d.,]+)")
        total_deuda = _extract(body, r"[Tt]otal\s*(?:[Dd]euda)?[:\s]+\$?\s*([\d.,]+)")
        avaluo = _extract(body, r"[Aa]val[úu]o[:\s]+\$?\s*([\d.,]+)")
        tipo_servicio = _extract(body, r"[Ss]ervicio[:\s]+([A-Za-z]+)")

        if "paz y salvo" in body.lower():
            estado = "PAZ Y SALVO"
        elif total_deuda:
            estado = "CON DEUDA"
        else:
            estado = ""

        return ImpuestoVehicularResult(
            placa=placa,
            departamento=self._departamento,
            marca=marca,
            modelo=modelo,
            cilindraje=cilindraje,
            tipo_servicio=tipo_servicio,
            avaluo=avaluo,
            total_deuda=total_deuda,
            vigencias_pendientes=vigencias,
            estado=estado,
            details=details,
        )


def _extract(text: str, pattern: str) -> str:
    """Extract first group from pattern in text, return empty string if not found."""
    m = re.search(pattern, text)
    return m.group(1).strip() if m else ""
