"""Multas Bogotá source — Bogotá traffic fines via WebFenix.

Queries Bogotá's Secretaría Distrital de Movilidad via the WebFenix portal.
The portal is an Angular SPA backed by Azure API Management endpoints.

Flow:
1. Navigate to https://webfenix.movilidadbogota.gov.co/#/consulta-pagos
2. Select document type and fill document number (or plate)
3. Solve simple math CAPTCHA (e.g., "7 + 4")
4. Click "Consultar"
5. Intercept API response from Azure APIM endpoint
6. Parse comparendos list

API endpoints discovered:
- TipoDocumento: GET /fx-mdmperstipodoc-sdm-prd/V1.0/TipoDocumento
- Consulta por doc: GET /fx-bancoconsultacompar-sdm-prd/V1.0/Obligacion/consulta-pagos/documento/{tipoDoc}/{numero}
- Consulta por placa: uses placa param
"""

from __future__ import annotations

import json
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

WEBFENIX_URL = "https://webfenix.movilidadbogota.gov.co/#/consulta-pagos"
APIM_BASE = "https://apim-fenix-sdm-prd.azure-api.net"
CONSULTA_ENDPOINT = (
    f"{APIM_BASE}/fx-bancoconsultacompar-sdm-prd/V1.0/Obligacion/"
    "consulta-pagos/documento"
)

# Map openquery DocumentType to WebFenix tipo_documento code
DOC_TYPE_MAP = {
    "CC": "C",    # Cédula de ciudadanía
    "CE": "E",    # Cédula de extranjería
    "NIT": "N",   # NIT
    "PA": "P",    # Pasaporte
    "TI": "T",    # Tarjeta de identidad
    "RC": "U",    # Registro civil
    "PPT": "PT",  # Permiso por protección temporal
    "CD": "D",    # Carnet diplomático
}


@register
class MultasBogotaSource(BaseSource):
    """Query Bogotá traffic fines from the WebFenix portal."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.multas_bogota",
            display_name="Tránsito Bogotá — Multas y Comparendos",
            description=(
                "Bogotá traffic fines and violations from the "
                "Secretaría Distrital de Movilidad (WebFenix)"
            ),
            country="CO",
            url=WEBFENIX_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.PLATE],
            requires_captcha=False,  # Simple math captcha, solved automatically
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in (DocumentType.CEDULA, DocumentType.PLATE):
            raise SourceError(
                "co.multas_bogota",
                f"Unsupported input type: {input.document_type}",
            )
        return self._query(
            input.document_number,
            input.document_type,
            audit=input.audit,
        )

    def _query(
        self,
        search_term: str,
        doc_type: DocumentType,
        audit: bool = False,
    ) -> MultasTransitoLocalResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector(
                "co.multas_bogota", doc_type.value, search_term
            )

        with browser.page(WEBFENIX_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                # Intercept the API response
                api_data: list[dict] = []

                def handle_response(response):
                    url = response.url
                    if "consulta-pagos/documento" in url and response.status == 200:
                        try:
                            body = response.text()
                            parsed = json.loads(body)
                            if isinstance(parsed, dict) and "value" in parsed:
                                api_data.extend(parsed["value"])
                            elif isinstance(parsed, list):
                                api_data.extend(parsed)
                        except Exception:
                            pass

                page.on("response", handle_response)

                # Wait for Angular SPA to render the form
                logger.info("Waiting for WebFenix form...")
                page.wait_for_selector(
                    "#identificacion, #mat-select-0",
                    state="visible",
                    timeout=15000,
                )
                page.wait_for_timeout(2000)

                if doc_type == DocumentType.PLATE:
                    return self._query_by_plate(
                        page, search_term, collector, api_data
                    )

                return self._query_by_document(
                    page, search_term, collector, api_data
                )

            except SourceError:
                raise
            except Exception as e:
                raise SourceError(
                    "co.multas_bogota", f"Query failed: {e}"
                ) from e

    def _query_by_document(
        self,
        page,
        doc_number: str,
        collector,
        api_data: list[dict],
    ) -> MultasTransitoLocalResult:
        """Query by document number (cédula)."""
        # Select document type (CC = Cédula de ciudadanía by default)
        tipo_select = page.locator("#mat-select-0")
        tipo_select.click()
        page.wait_for_timeout(500)

        # Click CC option
        cc_option = page.locator("mat-option").filter(
            has_text="Cédula de ciudadanía"
        )
        cc_option.click()
        page.wait_for_timeout(500)

        # Fill document number
        doc_input = page.locator("#identificacion")
        doc_input.fill(doc_number)
        logger.info("Filled document: %s", doc_number)

        if collector:
            collector.screenshot(page, "form_filled")

        # Solve math CAPTCHA
        self._solve_math_captcha(page)

        # Click Consultar
        submit_btn = page.get_by_role("button", name="Consultar")
        submit_btn.click()
        logger.info("Clicked Consultar")

        # Wait for API response
        page.wait_for_timeout(8000)

        if collector:
            collector.screenshot(page, "result")

        return self._parse_api_response(
            page, doc_number, collector, api_data
        )

    def _query_by_plate(
        self,
        page,
        plate: str,
        collector,
        api_data: list[dict],
    ) -> MultasTransitoLocalResult:
        """Query by vehicle plate number."""
        # Find the plate input (second input or labeled "Placa")
        plate_input = page.locator("#mat-input-1")
        plate_input.fill(plate.upper())
        logger.info("Filled plate: %s", plate)

        if collector:
            collector.screenshot(page, "form_filled_plate")

        # Solve math CAPTCHA
        self._solve_math_captcha(page)

        # Click Consultar
        submit_btn = page.get_by_role("button", name="Consultar")
        submit_btn.click()
        logger.info("Clicked Consultar")

        # Wait for API response
        page.wait_for_timeout(8000)

        if collector:
            collector.screenshot(page, "result")

        return self._parse_api_response(
            page, plate, collector, api_data
        )

    def _solve_math_captcha(self, page) -> None:
        """Solve the simple math CAPTCHA (e.g., '7 + 4')."""
        body_text = page.inner_text("body")
        match = re.search(r"(\d+)\s*([+\-×*÷])\s*(\d+)", body_text)
        if not match:
            logger.warning("Could not find math CAPTCHA")
            return

        a = int(match.group(1))
        op = match.group(2)
        b = int(match.group(3))

        if op in ("+",):
            result = a + b
        elif op in ("-",):
            result = a - b
        elif op in ("*", "×"):
            result = a * b
        elif op in ("÷",):
            result = a // b if b != 0 else 0
        else:
            result = a + b

        logger.info("Math CAPTCHA: %d %s %d = %d", a, op, b, result)
        captcha_input = page.locator('input[placeholder="Respuesta"]')
        captcha_input.fill(str(result))

    def _parse_api_response(
        self,
        page,
        search_term: str,
        collector,
        api_data: list[dict],
    ) -> MultasTransitoLocalResult:
        """Parse the intercepted API response into our model."""
        # If no API data intercepted, try parsing from DOM
        if not api_data:
            body_text = page.inner_text("body")
            if "no registra" in body_text.lower() or "no tiene" in body_text.lower():
                return MultasTransitoLocalResult(
                    queried_at=datetime.now(),
                    documento=search_term,
                    ciudad="Bogotá",
                    mensaje="No registra comparendos pendientes",
                )
            return MultasTransitoLocalResult(
                queried_at=datetime.now(),
                documento=search_term,
                ciudad="Bogotá",
                mensaje="Consulta realizada — sin datos de API interceptados",
            )

        # Parse API response
        nombre = ""
        comparendos: list[ComparendoLocal] = []
        total_deuda = 0.0

        for item in api_data:
            if not nombre and item.get("nombre"):
                nombre = item["nombre"]

            comp = ComparendoLocal(
                numero=str(item.get("numero", "")),
                tipo=str(item.get("tipo", "")),
                fecha=str(item.get("fecha", "")),
                fecha_notificacion=str(item.get("fechaNotificacion", "")),
                estado=str(item.get("estado", "")),
                placa=str(item.get("placa", "")),
                saldo=float(item.get("saldo", 0) or 0),
                interes=float(item.get("interes", 0) or 0),
                total=float(item.get("total", 0) or 0),
                medio_imposicion=str(item.get("medioImpocision", "")),
            )
            comparendos.append(comp)
            total_deuda += comp.total

        result = MultasTransitoLocalResult(
            queried_at=datetime.now(),
            documento=search_term,
            nombre=nombre,
            ciudad="Bogotá",
            total_comparendos=len(comparendos),
            total_deuda=total_deuda,
            comparendos=comparendos,
            mensaje=(
                f"Se encontraron {len(comparendos)} comparendo(s)"
                if comparendos
                else "No registra comparendos pendientes"
            ),
        )

        if collector:
            result_json = result.model_dump_json()
            result.audit = collector.generate_pdf(page, result_json)

        logger.info(
            "Bogotá results — %d comparendos, total=$%.0f, nombre=%s",
            result.total_comparendos,
            result.total_deuda,
            result.nombre,
        )
        return result
