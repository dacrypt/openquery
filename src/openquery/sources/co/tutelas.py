"""Tutelas source — Colombian constitutional protection actions lookup.

Queries the Rama Judicial for tutela (constitutional protection) actions
filed by or against a person or entity.

Flow:
1. Navigate to Rama Judicial tutela consultation page
2. Enter document number or name
3. Parse tutela records from result table

Source: https://consultaprocesos.ramajudicial.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.tutelas import TutelaEntry, TutelasResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

TUTELAS_URL = "https://consultaprocesos.ramajudicial.gov.co/"


@register
class TutelasSource(BaseSource):
    """Query Colombian tutela (constitutional protection) actions."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.tutelas",
            display_name="Rama Judicial — Consulta de Tutelas",
            description="Colombian tutela (constitutional protection) actions lookup",
            country="CO",
            url=TUTELAS_URL,
            supported_inputs=[
                DocumentType.CEDULA,
                DocumentType.NIT,
                DocumentType.CUSTOM,
            ],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.document_number.strip()
        name = input.extra.get("name", "").strip()
        if not search_term and not name:
            raise SourceError(
                "co.tutelas",
                "Provide a document number or name (extra.name)",
            )

        query_term = search_term if search_term else name
        tipo = {
            DocumentType.CEDULA: "cedula",
            DocumentType.NIT: "nit",
        }.get(input.document_type, "nombre")

        return self._query(query_term, tipo, audit=input.audit)

    def _query(
        self, query: str, tipo: str, audit: bool = False
    ) -> TutelasResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.tutelas", tipo, query)

        with browser.page(TUTELAS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_selector(
                    'input[type="text"], input[type="number"]',
                    timeout=15000,
                )
                page.wait_for_timeout(2000)

                # Try to select tutela-specific filter if available
                tipo_select = page.query_selector(
                    'select[id*="tipo"], select[name*="tipo"]'
                )
                if tipo_select:
                    try:
                        tipo_select.select_option(label="Tutela")
                    except Exception:
                        logger.debug("Could not select tutela filter")

                # Fill search input
                search_input = page.query_selector(
                    'input[type="text"][id*="nombre"], '
                    'input[type="text"][id*="razon"], '
                    'input[type="text"][id*="search"], '
                    'input[type="text"][id*="buscar"], '
                    'input[type="text"][name*="nombre"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError(
                        "co.tutelas", "Could not find search input field"
                    )

                search_input.fill(query)
                logger.info("Searching tutelas for: %s (type=%s)", query, tipo)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'a[id*="consultar"], a[id*="buscar"], '
                    'input[type="button"][id*="consultar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, query)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.tutelas", f"Query failed: {e}") from e

    def _parse_result(self, page, query: str) -> TutelasResult:
        """Parse the Rama Judicial result page for tutela records."""
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        no_records = any(phrase in body_lower for phrase in [
            "no se encontr",
            "sin resultados",
            "no hay resultados",
            "0 resultados",
            "no registra",
        ])

        nombre = ""
        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if any(label in lower for label in ["nombre", "razon social", "razón social"]):
                parts = stripped.split(":")
                if len(parts) > 1 and not nombre:
                    nombre = parts[1].strip()

        # Parse tutela records from table rows
        tutelas: list[TutelaEntry] = []
        rows = page.query_selector_all(
            "table tbody tr, .proceso-row, .resultado-item, .tutela-row"
        )

        for row in rows:
            text = row.inner_text()
            if not text.strip():
                continue

            text_lower = text.lower()
            # Only include rows that look like tutela records
            is_tutela = "tutela" in text_lower or not rows or len(rows) <= 20

            if is_tutela:
                cells = text.split("\t")
                if len(cells) >= 2:
                    tutela = TutelaEntry(
                        radicado=cells[0].strip() if cells else "",
                        accionante=cells[1].strip() if len(cells) > 1 else "",
                        accionado=cells[2].strip() if len(cells) > 2 else "",
                        derecho_invocado=cells[3].strip() if len(cells) > 3 else "",
                        fecha_presentacion=cells[4].strip() if len(cells) > 4 else "",
                        despacho=cells[5].strip() if len(cells) > 5 else "",
                        estado=cells[6].strip() if len(cells) > 6 else "",
                        fallo=cells[7].strip() if len(cells) > 7 else "",
                    )
                    tutelas.append(tutela)

        # Fallback: try extracting from key-value lines
        if not tutelas and not no_records:
            radicado = ""
            despacho = ""
            accionante = ""
            accionado = ""
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if any(k in lower for k in ["radicado", "radicación", "número"]):
                    parts = stripped.split(":")
                    if len(parts) > 1:
                        radicado = parts[1].strip()
                elif "despacho" in lower and ":" in stripped:
                    despacho = stripped.split(":", 1)[1].strip()
                elif "accionante" in lower and ":" in stripped:
                    accionante = stripped.split(":", 1)[1].strip()
                elif "accionado" in lower and ":" in stripped:
                    accionado = stripped.split(":", 1)[1].strip()
            if radicado or despacho:
                tutelas.append(TutelaEntry(
                    radicado=radicado,
                    despacho=despacho,
                    accionante=accionante,
                    accionado=accionado,
                ))

        total_tutelas = len(tutelas)

        mensaje = ""
        if no_records:
            mensaje = "No se encontraron tutelas"
        elif total_tutelas > 0:
            mensaje = f"Se encontraron {total_tutelas} tutela(s)"

        return TutelasResult(
            queried_at=datetime.now(),
            documento=query,
            nombre=nombre,
            total_tutelas=total_tutelas,
            tutelas=tutelas,
            mensaje=mensaje,
        )
