"""Multas Medellín source — Medellín traffic fines via Movilidad en Línea.

Queries Medellín's Secretaría de Movilidad via the portal-movilidad SPA.
The portal is an AngularJS SPA built by Quipux S.A.S with backend at /backavit/.

Portal: https://www.medellin.gov.co/portal-movilidad/
Backend: https://www.medellin.gov.co/backavit/
reCAPTCHA: v3 (invisible/score-based)

NOTE: The portal has been intermittently unavailable (503/connection resets).
The JSP sub-portals at /qxi_tramites/consultas/ are also frequently down.
This source implements the browser flow but may need refinement when the
portal is consistently accessible.

Flow:
1. Navigate to portal-movilidad SPA
2. Wait for AngularJS to render the consultation form
3. Fill document type, document number, or plate
4. Handle reCAPTCHA v3 (automatic/score-based)
5. Parse results from DOM or intercept API calls to /backavit/
"""

from __future__ import annotations

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

PORTAL_URL = "https://www.medellin.gov.co/portal-movilidad/"


@register
class MultasMedellinSource(BaseSource):
    """Query Medellín traffic fines from Movilidad en Línea."""

    def __init__(self, timeout: float = 45.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.multas_medellin",
            display_name="Tránsito Medellín — Multas y Comparendos",
            description=(
                "Medellín traffic fines and violations from the "
                "Secretaría de Movilidad (Movilidad en Línea)"
            ),
            country="CO",
            url=PORTAL_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.PLATE],
            requires_captcha=True,  # reCAPTCHA v3
            requires_browser=True,
            rate_limit_rpm=5,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in (DocumentType.CEDULA, DocumentType.PLATE):
            raise SourceError(
                "co.multas_medellin",
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
                "co.multas_medellin", doc_type.value, search_term
            )

        with browser.page(PORTAL_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                # Intercept API calls to /backavit/
                api_data: list[dict] = []

                def handle_response(response):
                    url = response.url
                    if "backavit" in url and response.status == 200:
                        try:
                            body = response.text()
                            import json

                            parsed = json.loads(body)
                            if isinstance(parsed, list):
                                api_data.extend(parsed)
                            elif isinstance(parsed, dict):
                                api_data.append(parsed)
                        except Exception:
                            pass

                page.on("response", handle_response)

                # Wait for AngularJS SPA to render
                logger.info("Waiting for Movilidad en Línea SPA...")
                try:
                    page.wait_for_selector(
                        "input, select, .form-control, [ng-model]",
                        state="visible",
                        timeout=20000,
                    )
                except Exception:
                    # SPA may not render visible elements quickly
                    logger.warning("SPA form elements not found, waiting longer...")
                    page.wait_for_timeout(10000)

                # Check if the page actually loaded
                body_text = page.inner_text("body")
                if not body_text.strip() or "can't be reached" in body_text:
                    raise SourceError(
                        "co.multas_medellin",
                        "Portal de Movilidad de Medellín no disponible",
                    )

                if collector:
                    collector.screenshot(page, "portal_loaded")

                # Try to navigate to estado de cuenta section
                # The SPA uses hash-based routing
                estado_cuenta_link = page.query_selector(
                    'a:has-text("Estado de cuenta"), '
                    'a:has-text("Consultar"), '
                    '[href*="estado-cuenta"]'
                )
                if estado_cuenta_link:
                    estado_cuenta_link.click()
                    page.wait_for_timeout(3000)
                    logger.info("Navigated to estado de cuenta")

                # Find and fill the search form
                # Look for document/plate input fields
                doc_input = page.query_selector(
                    'input[ng-model*="documento"], '
                    'input[ng-model*="identificacion"], '
                    'input[name*="documento"], '
                    'input[name*="numero"], '
                    'input[type="text"]:visible'
                )

                if doc_input:
                    doc_input.fill(search_term)
                    logger.info("Filled search term: %s", search_term)
                else:
                    raise SourceError(
                        "co.multas_medellin",
                        "No se encontró campo de búsqueda en el portal",
                    )

                if collector:
                    collector.screenshot(page, "form_filled")

                # Look for submit button
                submit_btn = page.query_selector(
                    'button:has-text("Consultar"), '
                    'button:has-text("Buscar"), '
                    'input[type="submit"], '
                    'button[type="submit"]'
                )

                if submit_btn:
                    submit_btn.click()
                    logger.info("Clicked submit")
                    page.wait_for_timeout(8000)
                else:
                    raise SourceError(
                        "co.multas_medellin",
                        "No se encontró botón de consulta",
                    )

                if collector:
                    collector.screenshot(page, "result")

                # Parse results from API data or DOM
                return self._parse_results(
                    page, search_term, collector, api_data
                )

            except SourceError:
                raise
            except Exception as e:
                raise SourceError(
                    "co.multas_medellin", f"Query failed: {e}"
                ) from e

    def _parse_results(
        self,
        page,
        search_term: str,
        collector,
        api_data: list[dict],
    ) -> MultasTransitoLocalResult:
        """Parse results from API data or DOM."""
        body_text = page.inner_text("body")

        # Check for "paz y salvo" / no results
        lower = body_text.lower()
        if any(
            phrase in lower
            for phrase in ["paz y salvo", "no registra", "no tiene", "sin resultados"]
        ):
            return MultasTransitoLocalResult(
                queried_at=datetime.now(),
                documento=search_term,
                ciudad="Medellín",
                mensaje="No registra comparendos pendientes",
            )

        # Try to parse from API data first
        if api_data:
            return self._parse_api_data(search_term, collector, api_data, page)

        # Fallback: parse from DOM tables
        return self._parse_dom(page, search_term, collector)

    def _parse_api_data(
        self,
        search_term: str,
        collector,
        api_data: list[dict],
        page,
    ) -> MultasTransitoLocalResult:
        """Parse results from intercepted API data."""
        comparendos: list[ComparendoLocal] = []
        nombre = ""
        total_deuda = 0.0

        for item in api_data:
            if not nombre:
                nombre = str(
                    item.get("nombre", item.get("nombreInfractor", ""))
                )
            comp = ComparendoLocal(
                numero=str(item.get("numero", item.get("comparendo", ""))),
                tipo=str(item.get("tipo", "")),
                fecha=str(item.get("fecha", item.get("fechaComparendo", ""))),
                estado=str(item.get("estado", "")),
                placa=str(item.get("placa", "")),
                saldo=float(item.get("saldo", item.get("valor", 0)) or 0),
                interes=float(item.get("interes", item.get("interesMora", 0)) or 0),
                total=float(item.get("total", item.get("valorTotal", 0)) or 0),
            )
            comparendos.append(comp)
            total_deuda += comp.total

        result = MultasTransitoLocalResult(
            queried_at=datetime.now(),
            documento=search_term,
            nombre=nombre,
            ciudad="Medellín",
            total_comparendos=len(comparendos),
            total_deuda=total_deuda,
            comparendos=comparendos,
            mensaje=f"Se encontraron {len(comparendos)} comparendo(s)",
        )

        if collector:
            result_json = result.model_dump_json()
            result.audit = collector.generate_pdf(page, result_json)

        return result

    def _parse_dom(
        self, page, search_term: str, collector
    ) -> MultasTransitoLocalResult:
        """Fallback: parse from DOM tables."""
        comparendos: list[ComparendoLocal] = []
        body_text = page.inner_text("body")
        total_deuda = 0.0

        # Try to find table rows
        rows = page.query_selector_all("table tbody tr")
        for row in rows:
            cells = row.query_selector_all("td")
            if len(cells) >= 4:
                comp = ComparendoLocal(
                    numero=(cells[0].inner_text() or "").strip(),
                    fecha=(cells[1].inner_text() or "").strip(),
                    estado=(cells[2].inner_text() or "").strip() if len(cells) > 2 else "",
                    placa=(cells[3].inner_text() or "").strip() if len(cells) > 3 else "",
                )
                # Try to extract value
                if len(cells) > 4:
                    val_text = (cells[4].inner_text() or "").strip()
                    val_clean = re.sub(r"[^\d.,]", "", val_text)
                    try:
                        comp.total = float(
                            val_clean.replace(".", "").replace(",", ".")
                        )
                    except ValueError:
                        pass
                total_deuda += comp.total
                comparendos.append(comp)

        # Extract total from body text
        m = re.search(r"Total[:\s]*\$\s*([\d.,]+)", body_text)
        if m:
            amount_str = m.group(1).replace(".", "").replace(",", ".")
            try:
                total_deuda = float(amount_str)
            except ValueError:
                pass

        result = MultasTransitoLocalResult(
            queried_at=datetime.now(),
            documento=search_term,
            ciudad="Medellín",
            total_comparendos=len(comparendos),
            total_deuda=total_deuda,
            comparendos=comparendos,
            mensaje=(
                f"Se encontraron {len(comparendos)} comparendo(s)"
                if comparendos
                else "Consulta realizada"
            ),
        )

        if collector:
            result_json = result.model_dump_json()
            result.audit = collector.generate_pdf(page, result_json)

        return result
