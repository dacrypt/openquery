"""Certificado de Tradicion source — Colombian property title certificate.

Queries the Superintendencia de Notariado y Registro for the Certificado
de Tradicion y Libertad by matricula inmobiliaria number.

Flow:
1. Navigate to SNR consultation page
2. Enter matricula inmobiliaria number
3. Parse property details and annotations from page

Source: https://www.supernotariado.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.certificado_tradicion import AnotacionTradicion, CertificadoTradicionResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SNR_URL = "https://www.supernotariado.gov.co/"


@register
class CertificadoTradicionSource(BaseSource):
    """Query Colombian property title certificate (Certificado de Tradicion y Libertad)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.certificado_tradicion",
            display_name="SNR \u2014 Certificado de Tradici\u00f3n y Libertad",
            description="Colombian property title certificate (Certificado de Tradici\u00f3n y Libertad)",
            country="CO",
            url=SNR_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=5,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError(
                "co.certificado_tradicion",
                f"Unsupported input type: {input.document_type}. Use CUSTOM with document_number=matricula.",
            )
        return self._query(input.document_number, audit=input.audit)

    def _query(self, matricula: str, audit: bool = False) -> CertificadoTradicionResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.certificado_tradicion", "matricula", matricula)

        with browser.page(SNR_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill matricula inmobiliaria number
                matricula_input = page.query_selector(
                    'input[type="text"][id*="matricula"], '
                    'input[type="text"][id*="numero"], '
                    'input[type="text"][id*="certificado"], '
                    'input[type="text"]'
                )
                if not matricula_input:
                    raise SourceError(
                        "co.certificado_tradicion", "Could not find matricula input field",
                    )

                matricula_input.fill(matricula)
                logger.info("Searching certificado tradicion for: %s", matricula)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    matricula_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, matricula)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.certificado_tradicion", f"Query failed: {e}") from e

    def _parse_result(self, page, matricula: str) -> CertificadoTradicionResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = CertificadoTradicionResult(
            queried_at=datetime.now(),
            matricula_inmobiliaria=matricula,
        )

        # Extract property details from page text
        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if ("circulo" in lower or "c\u00edrculo" in lower) and ":" in stripped:
                result.circulo_registral = stripped.split(":", 1)[1].strip()
            elif ("direcci" in lower or "predio" in lower) and ":" in stripped:
                result.direccion_predio = stripped.split(":", 1)[1].strip()
            elif "tipo" in lower and "predio" in lower and ":" in stripped:
                result.tipo_predio = stripped.split(":", 1)[1].strip()
            elif "departamento" in lower and ":" in stripped:
                result.departamento = stripped.split(":", 1)[1].strip()
            elif "municipio" in lower and ":" in stripped:
                result.municipio = stripped.split(":", 1)[1].strip()
            elif "propietario" in lower and ":" in stripped:
                result.propietario_actual = stripped.split(":", 1)[1].strip()

        # Extract annotations from tables
        rows = page.query_selector_all("table tr, .anotacion, .item-anotacion")

        anotaciones = []
        for row in rows:
            text = row.inner_text()
            if not text.strip():
                continue
            cells = text.split("\t")
            if len(cells) >= 3:
                anotaciones.append(AnotacionTradicion(
                    numero=cells[0].strip() if cells else "",
                    fecha=cells[1].strip() if len(cells) > 1 else "",
                    especificacion=cells[2].strip() if len(cells) > 2 else "",
                    radicacion=cells[3].strip() if len(cells) > 3 else "",
                    valor_acto=cells[4].strip() if len(cells) > 4 else "",
                    personas=cells[5].strip() if len(cells) > 5 else "",
                ))

        result.anotaciones = anotaciones
        result.total_anotaciones = len(anotaciones)

        # Check for liens/encumbrances
        body_lower = body_text.lower()
        result.tiene_gravamenes = any(
            phrase in body_lower
            for phrase in ["gravamen", "hipoteca", "embargo", "medida cautelar"]
        )

        result.mensaje = (
            f"Certificado {matricula}: {len(anotaciones)} anotacion(es) encontrada(s)"
        )

        return result
