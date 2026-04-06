"""Registro Civil source — Colombian civil registry certificate lookup.

Queries the Registraduría for civil registry certificate information.

Flow:
1. Navigate to Registraduría civil registry consultation page
2. Enter document number or serial
3. Submit and parse certificate details

Source: https://consultasrc.registraduria.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.registro_civil import RegistroCivilResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

REGISTRO_CIVIL_URL = "https://consultasrc.registraduria.gov.co/"


@register
class RegistroCivilSource(BaseSource):
    """Query Colombian civil registry certificates (Registraduría)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.registro_civil",
            display_name="Registraduría — Certificado Registro Civil",
            description="Colombian civil registry certificate lookup",
            country="CO",
            url=REGISTRO_CIVIL_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.document_number.strip()
        serial = input.extra.get("serial", "").strip()
        if not search_term and not serial:
            raise SourceError(
                "co.registro_civil",
                "Provide a document number or serial (extra.serial)",
            )

        return self._query(search_term, serial=serial, audit=input.audit)

    def _query(self, documento: str, serial: str = "", audit: bool = False) -> RegistroCivilResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("co.registro_civil", "cedula", documento)

        with browser.page(REGISTRO_CIVIL_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill document number
                doc_input = page.query_selector(
                    'input[type="text"][id*="nuip"], '
                    'input[type="text"][id*="cedula"], '
                    'input[type="text"][id*="numero"], '
                    'input[type="text"][name*="nuip"], '
                    'input[type="text"][name*="numero"], '
                    'input[type="text"]'
                )
                if not doc_input:
                    raise SourceError(
                        "co.registro_civil",
                        "Could not find document input field",
                    )

                doc_input.fill(documento)

                # Fill serial if provided
                if serial:
                    serial_input = page.query_selector(
                        'input[type="text"][id*="serial"], input[type="text"][name*="serial"]'
                    )
                    if serial_input:
                        serial_input.fill(serial)

                logger.info(
                    "Searching Registro Civil for: %s (serial=%s)",
                    documento,
                    serial,
                )

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'a[id*="consultar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    doc_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, documento)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.registro_civil", f"Query failed: {e}") from e

    def _parse_result(self, page, documento: str) -> RegistroCivilResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        nombre = ""
        fecha_nacimiento = ""
        lugar = ""
        sexo = ""
        serial = ""
        notaria = ""
        estado = ""
        tipo_documento = ""

        # Determine status
        if "vigente" in body_lower:
            estado = "Vigente"
        elif "anulado" in body_lower:
            estado = "Anulado"
        elif "no registra" in body_lower or "no se encontr" in body_lower:
            estado = "No registra"

        # Extract fields from key-value lines
        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nombre" in lower and ":" in stripped and not nombre:
                nombre = stripped.split(":", 1)[1].strip()
            elif ("fecha" in lower and "nacimiento" in lower) and ":" in stripped:
                fecha_nacimiento = stripped.split(":", 1)[1].strip()
            elif "lugar" in lower and ":" in stripped:
                lugar = stripped.split(":", 1)[1].strip()
            elif "sexo" in lower and ":" in stripped:
                sexo = stripped.split(":", 1)[1].strip()
            elif "serial" in lower and ":" in stripped:
                serial = stripped.split(":", 1)[1].strip()
            elif ("notar" in lower) and ":" in stripped:
                notaria = stripped.split(":", 1)[1].strip()
            elif "tipo" in lower and "documento" in lower and ":" in stripped:
                tipo_documento = stripped.split(":", 1)[1].strip()

        mensaje = ""
        if estado == "No registra":
            mensaje = "No se encontró registro civil"
        elif nombre:
            mensaje = f"Registro civil encontrado: {nombre}"
        else:
            mensaje = f"Registro civil consultado para documento {documento}"

        return RegistroCivilResult(
            queried_at=datetime.now(),
            nuip=documento,
            tipo_documento=tipo_documento,
            nombre=nombre,
            fecha_nacimiento=fecha_nacimiento,
            lugar_nacimiento=lugar,
            sexo=sexo,
            estado=estado,
            serial=serial,
            notaria=notaria,
            mensaje=mensaje,
        )
