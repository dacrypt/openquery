"""RUES source — Colombian unified business registry.

Queries the RUES (Registro Único Empresarial y Social) for business
registration information from Confecámaras.

Flow:
1. Navigate to RUES search page
2. Enter NIT, cédula, or business name
3. Parse results table

Source: https://www.rues.org.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.rues import RuesEstablecimiento, RuesResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

RUES_URL = "https://www.rues.org.co/"


@register
class RuesSource(BaseSource):
    """Query Colombian business registry (RUES / Confecámaras)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.rues",
            display_name="RUES — Registro Único Empresarial",
            description="Colombian unified business and social registry (Confecámaras)",
            country="CO",
            url=RUES_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.NIT, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.document_number.strip()
        name = input.extra.get("name", "").strip()
        if not search_term and not name:
            raise SourceError("co.rues", "Provide a NIT/cedula or name (extra.name)")

        query_term = search_term if search_term else name
        tipo = "nit" if input.document_type == DocumentType.NIT else (
            "cedula" if input.document_type == DocumentType.CEDULA else "nombre"
        )
        return self._query(query_term, tipo, audit=input.audit)

    def _query(self, query: str, tipo: str, audit: bool = False) -> RuesResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.rues", tipo, query)

        with browser.page(RUES_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                # Dismiss phishing warning dialog if present
                try:
                    close_btn = page.query_selector(
                        'button[aria-label*="Close"], button:has-text("×")'
                    )
                    if close_btn and close_btn.is_visible():
                        close_btn.click()
                        page.wait_for_timeout(500)
                except Exception:
                    pass

                # Fill search input (placeholder: "Digite su búsqueda")
                search_input = page.locator(
                    'input[placeholder*="búsqueda"], input[placeholder*="busqueda"], '
                    '#search, input[type="text"]'
                ).first
                if not search_input:
                    raise SourceError("co.rues", "Could not find search input field")

                search_input.fill(query)
                logger.info("Searching RUES for: %s", query)

                # Solve reCAPTCHA if present
                from openquery.core.captcha_middleware import solve_page_captchas
                solve_page_captchas(page)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit via "Buscar" button
                submit_btn = page.get_by_role("button", name="Buscar")
                submit_btn.click()

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, query, tipo)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.rues", f"Query failed: {e}") from e

    def _parse_result(self, page, query: str, tipo: str) -> RuesResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = RuesResult(
            queried_at=datetime.now(),
            documento=query,
            tipo_busqueda=tipo,
        )

        # Try to extract from result tables
        rows = page.query_selector_all("table tr, .resultado, .item-resultado")

        establecimientos = []
        for row in rows:
            text = row.inner_text()
            if not text.strip():
                continue
            cells = text.split("\t")
            if len(cells) >= 3:
                establecimientos.append(RuesEstablecimiento(
                    nombre=cells[0].strip() if cells else "",
                    matricula=cells[1].strip() if len(cells) > 1 else "",
                    estado=cells[2].strip() if len(cells) > 2 else "",
                    municipio=cells[3].strip() if len(cells) > 3 else "",
                ))

        result.establecimientos = establecimientos
        result.total_establecimientos = len(establecimientos)

        # Extract basic fields
        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "razón social" in lower and ":" in stripped:
                result.razon_social = stripped.split(":", 1)[1].strip()
            elif "nit" in lower and ":" in stripped and not result.nit:
                result.nit = stripped.split(":", 1)[1].strip()
            elif "cámara" in lower and ":" in stripped:
                result.camara_comercio = stripped.split(":", 1)[1].strip()
            elif "representante" in lower and ":" in stripped:
                result.representante_legal = stripped.split(":", 1)[1].strip()

        return result
