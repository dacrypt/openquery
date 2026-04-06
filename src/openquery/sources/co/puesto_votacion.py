"""Puesto de Votacion source — Colombian voting station lookup.

Queries the Registraduria Nacional del Estado Civil for voting station
assignment by cedula number.

Flow:
1. Navigate to Registraduria consultation page
2. Enter cedula number
3. Submit and parse voting station details

Source: https://wsp.registraduria.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.puesto_votacion import PuestoVotacionResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

REGISTRADURIA_URL = "https://wsp.registraduria.gov.co/"


@register
class PuestoVotacionSource(BaseSource):
    """Query Colombian voting station assignment (Registraduria)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.puesto_votacion",
            display_name="Registradur\u00eda \u2014 Puesto de Votaci\u00f3n",
            description="Colombian voting station lookup from Registradur\u00eda Nacional",
            country="CO",
            url=REGISTRADURIA_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError(
                "co.puesto_votacion",
                f"Unsupported document type: {input.document_type}. Use cedula.",
            )
        return self._query(input.document_number, audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> PuestoVotacionResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("co.puesto_votacion", "cedula", cedula)

        with browser.page(REGISTRADURIA_URL) as page:
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
                    'input[type="number"][id*="cedula"], '
                    'input[type="text"][name*="cedula"], '
                    'input[type="text"]'
                )
                if not doc_input:
                    raise SourceError("co.puesto_votacion", "Could not find cedula input field")

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

                # Parse result
                result = self._parse_result(page, cedula)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.puesto_votacion", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> PuestoVotacionResult:
        """Parse the Registraduria result page for voting station info."""
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        # Check for no records
        no_records = any(
            phrase in body_lower
            for phrase in [
                "no se encontr",
                "no aparece",
                "no registra",
                "c\u00e9dula no v\u00e1lida",
                "cedula no valida",
                "sin resultados",
            ]
        )

        # Extract fields from result
        nombre = ""
        departamento = ""
        municipio = ""
        puesto = ""
        direccion = ""
        mesa = ""

        for line in body_text.split("\n"):
            line_stripped = line.strip()
            line_lower = line_stripped.lower()

            if any(label in line_lower for label in ["nombre", "ciudadano"]):
                parts = line_stripped.split(":")
                if len(parts) > 1 and not nombre:
                    nombre = parts[1].strip()

            if "departamento" in line_lower:
                parts = line_stripped.split(":")
                if len(parts) > 1 and not departamento:
                    departamento = parts[1].strip()

            if "municipio" in line_lower:
                parts = line_stripped.split(":")
                if len(parts) > 1 and not municipio:
                    municipio = parts[1].strip()

            if any(label in line_lower for label in ["puesto", "lugar de votaci"]):
                parts = line_stripped.split(":")
                if len(parts) > 1 and not puesto:
                    puesto = parts[1].strip()

            if any(label in line_lower for label in ["direcci\u00f3n", "direccion"]):
                parts = line_stripped.split(":")
                if len(parts) > 1 and not direccion:
                    direccion = parts[1].strip()

            if "mesa" in line_lower:
                parts = line_stripped.split(":")
                if len(parts) > 1 and not mesa:
                    mesa = parts[1].strip()

        # Also try extracting from table rows
        if not puesto:
            rows = page.query_selector_all("table tr, .resultado td, .info-row")
            for row in rows:
                text = row.inner_text().strip()
                text_lower = text.lower()
                if "puesto" in text_lower and ":" in text:
                    puesto = text.split(":")[1].strip()
                elif "direcci" in text_lower and ":" in text:
                    direccion = text.split(":")[1].strip()
                elif "mesa" in text_lower and ":" in text:
                    mesa = text.split(":")[1].strip()

        mensaje = ""
        if no_records:
            mensaje = "No se encontr\u00f3 informaci\u00f3n de puesto de votaci\u00f3n"
        elif puesto:
            mensaje = f"Puesto de votaci\u00f3n: {puesto}"

        return PuestoVotacionResult(
            queried_at=datetime.now(),
            cedula=cedula,
            nombre=nombre,
            departamento=departamento,
            municipio=municipio,
            puesto=puesto,
            direccion=direccion,
            mesa=mesa,
            mensaje=mensaje,
        )
