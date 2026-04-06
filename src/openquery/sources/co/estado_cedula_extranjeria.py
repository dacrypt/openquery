"""Estado de Cédula de Extranjería source — foreign national ID verification.

Queries Migración Colombia for cédula de extranjería status.

Flow:
1. Navigate to Migración Colombia consultation page
2. Enter cédula de extranjería number and date of issuance
3. Submit and parse result (name, status, expiration, verification code)

Source: https://apps.migracioncolombia.gov.co/consultaCedulas/pages/home.jsf
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.estado_cedula_extranjeria import EstadoCedulaExtranjeriaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MIGRACION_URL = "https://apps.migracioncolombia.gov.co/consultaCedulas/pages/home.jsf"


@register
class EstadoCedulaExtranjeriaSource(BaseSource):
    """Query foreign national ID card status (Migración Colombia)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.estado_cedula_extranjeria",
            display_name="Migración Colombia — Cédula de Extranjería",
            description="Foreign national ID card (cédula de extranjería) status from Migración Colombia",  # noqa: E501
            country="CO",
            url=MIGRACION_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cedula = input.document_number.strip()
        if not cedula:
            raise SourceError(
                "co.estado_cedula_extranjeria", "Cédula de extranjería number is required"
            )

        fecha = input.extra.get("fecha_expedicion", "").strip()
        return self._query(cedula, fecha, audit=input.audit)

    def _query(
        self,
        cedula: str,
        fecha_expedicion: str = "",
        audit: bool = False,
    ) -> EstadoCedulaExtranjeriaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("co.estado_cedula_extranjeria", "cedula_extranjeria", cedula)

        with browser.page(MIGRACION_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill cédula de extranjería number
                cedula_input = page.query_selector(
                    'input[type="text"][id*="cedula"], '
                    'input[type="text"][id*="numero"], '
                    'input[type="text"][name*="cedula"], '
                    'input[type="text"][name*="numero"], '
                    'input[type="text"]'
                )
                if not cedula_input:
                    raise SourceError(
                        "co.estado_cedula_extranjeria", "Could not find cédula input field"
                    )

                cedula_input.fill(cedula)

                # Fill date if provided
                if fecha_expedicion:
                    date_input = page.query_selector(
                        'input[type="text"][id*="fecha"], '
                        'input[type="date"][id*="fecha"], '
                        'input[type="text"][name*="fecha"]'
                    )
                    if date_input:
                        date_input.fill(fecha_expedicion)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'a[id*="consultar"], input[id*="consultar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    cedula_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cedula, fecha_expedicion)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.estado_cedula_extranjeria", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str, fecha: str) -> EstadoCedulaExtranjeriaResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        estado = "Desconocido"
        nombre = ""
        nacionalidad = ""
        fecha_vencimiento = ""
        codigo_verificacion = ""

        if "vigente" in body_lower:
            estado = "Vigente"
        elif "vencid" in body_lower:
            estado = "Vencida"
        elif "cancelad" in body_lower:
            estado = "Cancelada"
        elif "no registra" in body_lower or "no se encontr" in body_lower:
            estado = "No registrada"

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if ("nombre" in lower or "titular" in lower) and ":" in stripped and not nombre:
                nombre = stripped.split(":", 1)[1].strip()
            elif "nacionalidad" in lower and ":" in stripped and not nacionalidad:
                nacionalidad = stripped.split(":", 1)[1].strip()
            elif "vencimiento" in lower and ":" in stripped and not fecha_vencimiento:
                fecha_vencimiento = stripped.split(":", 1)[1].strip()
            elif (
                ("verificaci" in lower or "código" in lower)
                and ":" in stripped
                and not codigo_verificacion
            ):
                codigo_verificacion = stripped.split(":", 1)[1].strip()

        return EstadoCedulaExtranjeriaResult(
            queried_at=datetime.now(),
            cedula_extranjeria=cedula,
            fecha_expedicion=fecha,
            fecha_vencimiento=fecha_vencimiento,
            estado=estado,
            nombre=nombre,
            nacionalidad=nacionalidad,
            codigo_verificacion=codigo_verificacion,
            mensaje=f"Cédula de extranjería {cedula}: {estado}",
        )
