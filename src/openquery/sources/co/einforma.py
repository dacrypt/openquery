"""eInforma source — Colombian business intelligence and company information.

Queries eInforma Colombia for company information by NIT or company name.

Flow:
1. Navigate to eInforma search page
2. Enter NIT or company name
3. Parse company details from result page

Source: https://www.einforma.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.einforma import EinformaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

EINFORMA_URL = "https://www.einforma.co/"


@register
class EinformaSource(BaseSource):
    """Query Colombian business intelligence (eInforma)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.einforma",
            display_name="eInforma \u2014 Inteligencia Empresarial",
            description="Colombian business intelligence and company information (eInforma)",
            country="CO",
            url=EINFORMA_URL,
            supported_inputs=[DocumentType.NIT, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.document_number.strip()
        name = input.extra.get("name", "").strip()
        if not search_term and not name:
            raise SourceError("co.einforma", "Provide a NIT or company name (extra.name)")

        query_term = search_term if search_term else name
        tipo = "nit" if input.document_type == DocumentType.NIT else "nombre"
        return self._query(query_term, tipo, audit=input.audit)

    def _query(self, query: str, tipo: str, audit: bool = False) -> EinformaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.einforma", tipo, query)

        with browser.page(EINFORMA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                # Fill search input — exact IDs from site: #search (mobile), #search2 (desktop)
                search_input = page.query_selector(
                    '#search, #search2, '
                    'input[type="search"], '
                    'input[type="text"][placeholder*="empresa"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("co.einforma", "Could not find search input field")

                search_input.fill(query)
                logger.info("Searching eInforma for: %s (type=%s)", query, tipo)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit — use the button or press Enter (JS-based form action)
                submit_btn = page.query_selector(
                    '#boton_buscador_nacional, '
                    'input[type="submit"].searchbox-submit, '
                    'input[type="button"].searchbox-submit'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                # Click first result if we get a list
                first_link = page.query_selector(
                    'a[href*="empresa"], a[href*="company"], '
                    '.resultado a, .result-item a, '
                    'table tbody tr a'
                )
                if first_link:
                    first_link.click()
                    page.wait_for_timeout(3000)

                    if collector:
                        collector.screenshot(page, "detail")

                result = self._parse_result(page, query, tipo)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.einforma", f"Query failed: {e}") from e

    def _parse_result(self, page, query: str, tipo: str) -> EinformaResult:
        """Parse the eInforma result page for company details."""
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        no_records = any(phrase in body_lower for phrase in [
            "no se encontr",
            "sin resultados",
            "no hay resultados",
            "0 resultados",
            "no hemos encontrado",
        ])

        result = EinformaResult(
            queried_at=datetime.now(),
            query=query,
            tipo_busqueda=tipo,
        )

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()

            if any(label in lower for label in ["raz\u00f3n social", "razon social", "nombre empresa"]):
                parts = stripped.split(":")
                if len(parts) > 1 and not result.razon_social:
                    result.razon_social = parts[1].strip()

            elif "nit" in lower and ":" in stripped and not result.nit:
                result.nit = stripped.split(":", 1)[1].strip()

            elif "estado" in lower and ":" in stripped and not result.estado:
                result.estado = stripped.split(":", 1)[1].strip()

            elif any(label in lower for label in ["actividad econ", "ciiu", "objeto social"]):
                parts = stripped.split(":")
                if len(parts) > 1 and not result.actividad_economica:
                    result.actividad_economica = parts[1].strip()

            elif any(label in lower for label in ["tama\u00f1o", "tamano", "tipo empresa"]):
                parts = stripped.split(":")
                if len(parts) > 1 and not result.tamano_empresa:
                    result.tamano_empresa = parts[1].strip()

            elif any(label in lower for label in ["direcci\u00f3n", "direccion"]):
                parts = stripped.split(":")
                if len(parts) > 1 and not result.direccion:
                    result.direccion = parts[1].strip()

            elif "municipio" in lower and ":" in stripped and not result.municipio:
                result.municipio = stripped.split(":", 1)[1].strip()

            elif "departamento" in lower and ":" in stripped and not result.departamento:
                result.departamento = stripped.split(":", 1)[1].strip()

            elif any(label in lower for label in ["tel\u00e9fono", "telefono", "tel:"]):
                parts = stripped.split(":")
                if len(parts) > 1 and not result.telefono:
                    result.telefono = parts[1].strip()

            elif "representante" in lower and ":" in stripped and not result.representante_legal:
                result.representante_legal = stripped.split(":", 1)[1].strip()

            elif any(label in lower for label in ["fecha constituci", "fecha de constituci", "fundaci"]):
                parts = stripped.split(":")
                if len(parts) > 1 and not result.fecha_constitucion:
                    result.fecha_constitucion = parts[1].strip()

        # Also try table/card extraction
        if not result.razon_social:
            rows = page.query_selector_all(
                "table tr, .company-detail, .info-row, .dato, dl dt, dl dd"
            )
            for row in rows:
                text = row.inner_text().strip()
                text_lower = text.lower()
                if "raz\u00f3n social" in text_lower and ":" in text:
                    result.razon_social = text.split(":", 1)[1].strip()
                elif "nit" in text_lower and ":" in text and not result.nit:
                    result.nit = text.split(":", 1)[1].strip()

        result.encontrado = bool(result.razon_social or result.nit) and not no_records

        if no_records:
            result.mensaje = "No se encontr\u00f3 informaci\u00f3n de la empresa"
        elif result.encontrado:
            result.mensaje = f"Empresa encontrada: {result.razon_social or result.nit}"

        return result
