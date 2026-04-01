"""Validar Policía source — verify if a police officer is legitimate.

Queries the Policía Nacional to validate a police officer by their
cédula, badge number (placa), and ID card (carnet).

Flow:
1. Navigate to the police consultation page (same as RNMC)
2. Click the "Validar Policía" section/button
3. Enter officer's cédula, placa, and carnet number
4. Submit and parse validation result

Source: https://srvcnpc.policia.gov.co/PSC/frm_cnp_consulta.aspx
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.validar_policia import ValidarPoliciaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

POLICIA_URL = "https://srvcnpc.policia.gov.co/PSC/frm_cnp_consulta.aspx"


@register
class ValidarPoliciaSource(BaseSource):
    """Validate a police officer's identity (Policía Nacional)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.validar_policia",
            display_name="Policía Nacional — Validar Policía",
            description="Validate a police officer is legitimate by cédula, badge (placa), and ID card (carnet)",
            country="CO",
            url=POLICIA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cedula = input.document_number.strip()
        placa = input.extra.get("placa_policia", "").strip()
        carnet = input.extra.get("carnet", "").strip()

        if not cedula:
            raise SourceError("co.validar_policia", "Officer's cédula number is required")
        if not placa and not carnet:
            raise SourceError(
                "co.validar_policia",
                "Must provide extra['placa_policia'] and/or extra['carnet']",
            )

        return self._query(cedula, placa, carnet, audit=input.audit)

    def _query(self, cedula: str, placa: str, carnet: str, audit: bool = False) -> ValidarPoliciaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.validar_policia", "cedula", cedula)

        with browser.page(POLICIA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_selector('input[type="text"], select', timeout=15000)
                page.wait_for_timeout(2000)

                # Look for the "Validar Policía" tab/button and click it
                validar_tab = page.query_selector(
                    'a[href*="validar"], a[id*="validar"], '
                    'button[id*="validar"], input[id*="validar"], '
                    'a:text("Validar"), a:text("validar")'
                )
                if validar_tab:
                    validar_tab.click()
                    page.wait_for_timeout(2000)

                # Fill cédula
                cedula_input = page.query_selector(
                    'input[type="text"][id*="cedula"], '
                    'input[type="text"][id*="documento"], '
                    'input[type="text"][id*="numero"], '
                    'input[type="text"]'
                )
                if not cedula_input:
                    raise SourceError("co.validar_policia", "Could not find cédula input field")

                cedula_input.fill(cedula)

                # Fill placa (badge number)
                if placa:
                    placa_input = page.query_selector(
                        'input[type="text"][id*="placa"], '
                        'input[type="text"][name*="placa"]'
                    )
                    if placa_input:
                        placa_input.fill(placa)

                # Fill carnet
                if carnet:
                    carnet_input = page.query_selector(
                        'input[type="text"][id*="carnet"], '
                        'input[type="text"][name*="carnet"]'
                    )
                    if carnet_input:
                        carnet_input.fill(carnet)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'input[id*="consultar"], input[id*="validar"], '
                    'button[id*="consultar"], button[id*="validar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    cedula_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cedula, placa, carnet)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.validar_policia", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str, placa: str, carnet: str) -> ValidarPoliciaResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        es_activo = False
        nombre = ""
        grado = ""
        unidad = ""
        mensaje = ""

        if any(phrase in body_lower for phrase in [
            "es un funcionario activo",
            "policía activo",
            "policia activo",
            "validación exitosa",
            "validacion exitosa",
            "sí pertenece",
            "si pertenece",
        ]):
            es_activo = True
            mensaje = "El funcionario es un policía activo"
        elif any(phrase in body_lower for phrase in [
            "no pertenece",
            "no es funcionario",
            "no se encontr",
            "no registra",
            "datos no coinciden",
        ]):
            es_activo = False
            mensaje = "No se pudo validar como policía activo"

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nombre" in lower and ":" in stripped and not nombre:
                nombre = stripped.split(":", 1)[1].strip()
            elif ("grado" in lower or "rango" in lower) and ":" in stripped and not grado:
                grado = stripped.split(":", 1)[1].strip()
            elif "unidad" in lower and ":" in stripped and not unidad:
                unidad = stripped.split(":", 1)[1].strip()

        return ValidarPoliciaResult(
            queried_at=datetime.now(),
            cedula=cedula,
            placa=placa,
            carnet=carnet,
            es_policia_activo=es_activo,
            nombre=nombre,
            grado=grado,
            unidad=unidad,
            mensaje=mensaje,
        )
