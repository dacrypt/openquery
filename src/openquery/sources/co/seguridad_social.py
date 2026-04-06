"""Seguridad Social source — Colombian integrated social security status.

Queries Mi Seguridad Social for affiliation records covering health,
pension, labor risks, and compensation fund.

Flow:
1. Navigate to Mi Seguridad Social consultation page
2. Select document type and enter number
3. Submit and parse affiliation records

Source: https://www.miseguridadsocial.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.seguridad_social import AfiliacionSS, SeguridadSocialResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SEGURIDAD_SOCIAL_URL = "https://www.miseguridadsocial.gov.co/"


@register
class SeguridadSocialSource(BaseSource):
    """Query Colombian social security status (PILA)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.seguridad_social",
            display_name="PILA — Seguridad Social Integral",
            description="Colombian integrated social security status (health, pension, labor risks)",  # noqa: E501
            country="CO",
            url=SEGURIDAD_SOCIAL_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.NIT],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in (DocumentType.CEDULA, DocumentType.NIT):
            raise SourceError(
                "co.seguridad_social",
                f"Unsupported input type: {input.document_type}",
            )

        tipo = "cedula" if input.document_type == DocumentType.CEDULA else "nit"
        return self._query(input.document_number, tipo, audit=input.audit)

    def _query(self, documento: str, tipo: str, audit: bool = False) -> SeguridadSocialResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("co.seguridad_social", tipo, documento)

        with browser.page(SEGURIDAD_SOCIAL_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_selector(
                    'input[type="text"], input[type="number"], select',
                    timeout=15000,
                )
                page.wait_for_timeout(2000)

                # Try to select document type
                tipo_select = page.query_selector(
                    'select[id*="tipo"], select[name*="tipo"], '
                    'select[id*="document"], select[name*="document"]'
                )
                if tipo_select:
                    if tipo == "cedula":
                        tipo_select.select_option(label="Cédula de Ciudadanía")
                    elif tipo == "nit":
                        tipo_select.select_option(label="NIT")

                # Fill document number
                doc_input = page.query_selector(
                    'input[type="text"][id*="numero"], '
                    'input[type="text"][id*="document"], '
                    'input[type="number"][id*="numero"], '
                    'input[type="text"][name*="numero"], '
                    'input[type="text"]'
                )
                if not doc_input:
                    raise SourceError(
                        "co.seguridad_social",
                        "Could not find document number input field",
                    )

                doc_input.fill(documento)
                logger.info("Filled document: %s (type=%s)", documento, tipo)

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

                result = self._parse_result(page, documento, tipo)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.seguridad_social", f"Query failed: {e}") from e

    def _parse_result(self, page, documento: str, tipo: str) -> SeguridadSocialResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        nombre = ""
        empleador = ""
        ultimo_periodo = ""
        cotizante_activo = False

        # Extract key-value pairs
        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nombre" in lower and ":" in stripped and not nombre:
                nombre = stripped.split(":", 1)[1].strip()
            elif "empleador" in lower and ":" in stripped:
                empleador = stripped.split(":", 1)[1].strip()
            elif ("periodo" in lower or "período" in lower) and ":" in stripped:
                ultimo_periodo = stripped.split(":", 1)[1].strip()

        if "activo" in body_lower or "cotizante activo" in body_lower:
            cotizante_activo = True

        # Parse affiliation records for each subsystem
        afiliaciones: list[AfiliacionSS] = []

        subsystems = [
            ("Salud", ["salud", "eps"]),
            ("Pensión", ["pensión", "pension", "afp"]),
            ("Riesgos Laborales", ["riesgos laborales", "arl"]),
            ("Caja Compensación", ["caja de compensación", "caja compensación", "ccf"]),
        ]

        rows = page.query_selector_all(
            "table tbody tr, .afiliacion-row, .resultado-item, .card, .panel-body"
        )

        for row in rows:
            text = row.inner_text()
            text_lower = text.lower()
            for tipo_ss, keywords in subsystems:
                if any(kw in text_lower for kw in keywords):
                    admin = ""
                    estado = ""
                    regimen = ""
                    parts = text.split("\n")
                    for part in parts:
                        part_stripped = part.strip()
                        part_lower = part_stripped.lower()
                        if any(
                            kw in part_lower
                            for kw in ["administradora", "entidad", "eps", "afp", "arl"]
                        ):
                            if ":" in part_stripped:
                                admin = part_stripped.split(":", 1)[1].strip()
                            elif not admin:
                                admin = part_stripped
                        elif "estado" in part_lower and ":" in part_stripped:
                            estado = part_stripped.split(":", 1)[1].strip()
                        elif (
                            "régimen" in part_lower or "regimen" in part_lower
                        ) and ":" in part_stripped:
                            regimen = part_stripped.split(":", 1)[1].strip()
                    afiliaciones.append(
                        AfiliacionSS(
                            tipo=tipo_ss,
                            administradora=admin,
                            estado=estado,
                            regimen=regimen,
                        )
                    )
                    break

        # Fallback: parse from key-value lines if no table rows matched
        if not afiliaciones:
            for tipo_ss, keywords in subsystems:
                for line in body_text.split("\n"):
                    lower = line.strip().lower()
                    if any(kw in lower for kw in keywords):
                        afiliaciones.append(AfiliacionSS(tipo=tipo_ss))
                        break

        no_records = any(
            phrase in body_lower
            for phrase in [
                "no se encontr",
                "sin resultados",
                "no registra",
                "no hay información",
            ]
        )

        mensaje = ""
        if no_records:
            mensaje = "No se encontró información de seguridad social"
        elif afiliaciones:
            mensaje = f"Se encontraron {len(afiliaciones)} afiliación(es)"

        return SeguridadSocialResult(
            queried_at=datetime.now(),
            documento=documento,
            tipo_documento=tipo,
            nombre=nombre,
            afiliaciones=afiliaciones,
            cotizante_activo=cotizante_activo,
            ultimo_periodo_pagado=ultimo_periodo,
            empleador=empleador,
            mensaje=mensaje,
        )
