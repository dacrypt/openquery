"""SUNAT RUC source — Peruvian tax registry.

Queries SUNAT for RUC (tax ID) registration status, business info, and regime.
Protected by reCAPTCHA v3.

Flow:
1. Navigate to RUC consultation page
2. Enter RUC, DNI, or business name
3. Submit search
4. Parse result table
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.sunat_ruc import SunatRucResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUNAT_URL = (
    "https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/FrameCriterioBusquedaMovil.jsp"
)


@register
class SunatRucSource(BaseSource):
    """Query Peruvian tax registry (SUNAT RUC)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.sunat_ruc",
            display_name="SUNAT — Consulta RUC",
            description="Peruvian tax registry: RUC status, business info, and tax regime",
            country="PE",
            url=SUNAT_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        ruc = input.extra.get("ruc", "")
        dni = input.extra.get("dni", "")
        name = input.extra.get("name", "")
        if not ruc and not dni and not name:
            raise SourceError(
                "pe.sunat_ruc",
                "Must provide extra.ruc, extra.dni, or extra.name",
            )
        return self._query(ruc=ruc, dni=dni, name=name, audit=input.audit)

    def _query(
        self,
        ruc: str = "",
        dni: str = "",
        name: str = "",
        audit: bool = False,
    ) -> SunatRucResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("pe.sunat_ruc", "custom", ruc or dni or name)

        with browser.page(SUNAT_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                if ruc:
                    # Click "Por RUC" tab and fill
                    ruc_tab = page.query_selector("#btnPorRuc")
                    if ruc_tab:
                        ruc_tab.click()
                        page.wait_for_timeout(500)
                    ruc_input = page.query_selector("#txtRuc, input[name*='ruc']")
                    if ruc_input:
                        ruc_input.fill(ruc)
                        logger.info("Filled RUC: %s", ruc)
                elif dni:
                    # Click "Por Documento" tab and fill
                    doc_tab = page.query_selector("#btnPorDocumento")
                    if doc_tab:
                        doc_tab.click()
                        page.wait_for_timeout(500)
                    dni_input = page.query_selector(
                        "#txtNumeroDocumento, input[name*='documento']"
                    )
                    if dni_input:
                        dni_input.fill(dni)
                        logger.info("Filled DNI: %s", dni)
                elif name:
                    # Click "Por Razon Social" tab and fill
                    name_tab = page.query_selector("#btnPorRazonSocial")
                    if name_tab:
                        name_tab.click()
                        page.wait_for_timeout(500)
                    name_input = page.query_selector(
                        "#txtNombreRazonSocial, input[name*='razon']"
                    )
                    if name_input:
                        name_input.fill(name)
                        logger.info("Filled name: %s", name)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit — exact ID: #btnAceptar
                submit = page.query_selector(
                    "#btnAceptar, #btnBuscar, "
                    "input[value='Buscar'], "
                    "button:has-text('Buscar')"
                )
                if submit:
                    submit.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector(
                    "table, .list-group, .resultado, #divResultado",
                    timeout=15000,
                )

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, ruc, dni, name)

                if collector:
                    result.audit = collector.generate_pdf(
                        page, result.model_dump_json()
                    )

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pe.sunat_ruc", f"Query failed: {e}") from e

    def _parse_result(
        self, page, ruc: str, dni: str, name: str,
    ) -> SunatRucResult:
        """Parse the SUNAT RUC result page."""
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SunatRucResult(
            queried_at=datetime.now(),
            ruc=ruc,
        )

        field_patterns = [
            (r"RUC[:\s]+(\d{11})", "ruc"),
            (r"(?:Raz[oó]n Social|Nombre)[:\s]+([^\n]+)", "razon_social"),
            (r"Estado[:\s]+([^\n]+)", "estado"),
            (r"Condici[oó]n[:\s]+([^\n]+)", "condicion"),
            (r"(?:Domicilio|Direcci[oó]n)[:\s]+([^\n]+)", "direccion"),
            (r"Actividad[:\s]+([^\n]+)", "actividad_economica"),
            (r"(?:R[eé]gimen|Sistema)[:\s]+([^\n]+)", "regimen"),
            (r"Tipo[:\s]+([^\n]+)", "tipo_contribuyente"),
            (r"(?:Fecha de Inscripci[oó]n|Inicio)[:\s]+([^\n]+)", "fecha_inscripcion"),
        ]

        for pattern, field in field_patterns:
            m = re.search(pattern, body_text, re.IGNORECASE)
            if m:
                setattr(result, field, m.group(1).strip())

        return result
