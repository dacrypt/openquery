"""Nombre Completo source — Colombian full name lookup by document number.

Queries the Registraduría Nacional del Estado Civil for the full name
associated with a cédula number.

Flow:
1. Navigate to Registraduría consultation page
2. Enter cédula number
3. Submit and parse full name, splitting into components

Source: https://consultasrc.registraduria.gov.co/ProyectoSCCRC/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.nombre_completo import NombreCompletoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

REGISTRADURIA_URL = "https://consultasrc.registraduria.gov.co/ProyectoSCCRC/"


@register
class NombreCompletoSource(BaseSource):
    """Query Colombian full name by document number (Registraduría)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.nombre_completo",
            display_name="Nombre Completo \u2014 Consulta de Nombre",
            description="Colombian full name lookup by document number",
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
                "co.nombre_completo",
                f"Unsupported document type: {input.document_type}. Use cedula.",
            )
        return self._query(input.document_number, audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> NombreCompletoResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("co.nombre_completo", "cedula", cedula)

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
                    raise SourceError("co.nombre_completo", "Could not find cedula input field")

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
                raise SourceError("co.nombre_completo", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> NombreCompletoResult:
        """Parse the Registraduría result page for full name info."""
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
                "cédula no válida",
                "cedula no valida",
                "sin resultados",
            ]
        )

        nombre_completo = ""

        # Extract name from result page
        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()

            if any(
                label in lower
                for label in ["nombre completo", "nombre del ciudadano", "nombres y apellidos"]
            ):
                parts = stripped.split(":")
                if len(parts) > 1 and not nombre_completo:
                    nombre_completo = parts[1].strip()

            if not nombre_completo and any(label in lower for label in ["nombre", "ciudadano"]):
                parts = stripped.split(":")
                if len(parts) > 1:
                    nombre_completo = parts[1].strip()

        # Also try extracting from table rows / result containers
        if not nombre_completo:
            rows = page.query_selector_all("table tr, .resultado td, .info-row, .dato")
            for row in rows:
                text = row.inner_text().strip()
                text_lower = text.lower()
                if any(k in text_lower for k in ["nombre", "ciudadano"]) and ":" in text:
                    nombre_completo = text.split(":", 1)[1].strip()
                    break

        # Split full name into components
        primer_nombre = ""
        segundo_nombre = ""
        primer_apellido = ""
        segundo_apellido = ""

        if nombre_completo:
            parts = nombre_completo.split()
            if len(parts) == 4:
                primer_apellido = parts[0]
                segundo_apellido = parts[1]
                primer_nombre = parts[2]
                segundo_nombre = parts[3]
            elif len(parts) == 3:
                primer_apellido = parts[0]
                segundo_apellido = parts[1]
                primer_nombre = parts[2]
            elif len(parts) == 2:
                primer_apellido = parts[0]
                primer_nombre = parts[1]
            elif len(parts) >= 5:
                # Assume: apellido1 apellido2 nombre1 nombre2 ...
                primer_apellido = parts[0]
                segundo_apellido = parts[1]
                primer_nombre = parts[2]
                segundo_nombre = " ".join(parts[3:])

        encontrado = bool(nombre_completo) and not no_records

        mensaje = ""
        if no_records:
            mensaje = "No se encontró información para esta cédula"
        elif encontrado:
            mensaje = f"Nombre encontrado: {nombre_completo}"

        return NombreCompletoResult(
            queried_at=datetime.now(),
            documento=cedula,
            tipo_documento="CC",
            nombre_completo=nombre_completo,
            primer_nombre=primer_nombre,
            segundo_nombre=segundo_nombre,
            primer_apellido=primer_apellido,
            segundo_apellido=segundo_apellido,
            encontrado=encontrado,
            fuente="Registraduría Nacional",
            mensaje=mensaje,
        )
