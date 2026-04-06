"""Funcion Judicial source — Ecuador judicial process lookup.

Queries Ecuador's Consejo de la Judicatura for judicial processes
by cedula or case number.

Flow:
1. Navigate to the judicial process consultation page
2. Enter cedula, name, or case number
3. Submit and parse results

Source: https://procesosjudiciales.funcionjudicial.gob.ec/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ec.funcion_judicial import FuncionJudicialResult, ProcesoJudicial
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

JUDICIAL_URL = "https://procesosjudiciales.funcionjudicial.gob.ec/"


@register
class FuncionJudicialSource(BaseSource):
    """Query Ecuador judicial processes from Consejo de la Judicatura."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ec.funcion_judicial",
            display_name="Funcion Judicial — Procesos Judiciales",
            description="Ecuador judicial process search from Consejo de la Judicatura",
            country="EC",
            url=JUDICIAL_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in (DocumentType.CEDULA, DocumentType.CUSTOM):
            raise SourceError(
                "ec.funcion_judicial", f"Unsupported input type: {input.document_type}"
            )

        documento = input.document_number.strip()
        nombre = input.extra.get("nombre", "").strip()
        numero_causa = input.extra.get("numero_causa", "").strip()

        if not documento and not nombre and not numero_causa:
            raise SourceError(
                "ec.funcion_judicial",
                "Must provide document_number, extra['nombre'], or extra['numero_causa']",
            )

        return self._query(documento, nombre=nombre, numero_causa=numero_causa, audit=input.audit)

    def _query(
        self,
        documento: str,
        nombre: str = "",
        numero_causa: str = "",
        audit: bool = False,
    ) -> FuncionJudicialResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector(
                "ec.funcion_judicial", "cedula", documento or nombre or numero_causa
            )

        with browser.page(JUDICIAL_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Determine search type and fill appropriate field
                if numero_causa:
                    causa_input = page.query_selector(
                        'input[id*="causa"], input[name*="causa"], '
                        'input[placeholder*="causa"], input[id*="juicio"]'
                    )
                    if causa_input:
                        causa_input.fill(numero_causa)
                elif documento:
                    doc_input = page.query_selector(
                        'input[id*="cedula"], input[id*="actor"], '
                        'input[name*="cedula"], input[id*="demandado"], '
                        'input[type="text"]'
                    )
                    if doc_input:
                        doc_input.fill(documento)
                elif nombre:
                    name_input = page.query_selector(
                        'input[id*="nombre"], input[name*="nombre"], '
                        'input[placeholder*="nombre"], input[type="text"]'
                    )
                    if name_input:
                        name_input.fill(nombre)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'button:has-text("Consultar"), button:has-text("Buscar")'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, documento or nombre or numero_causa)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ec.funcion_judicial", f"Query failed: {e}") from e

    def _parse_result(self, page, documento: str) -> FuncionJudicialResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        procesos: list[ProcesoJudicial] = []

        # Try to find table rows with process data
        rows = page.query_selector_all("table tbody tr, .resultado-fila, .proceso-item")
        for row in rows:
            try:
                cells = row.query_selector_all("td, .campo")
                if len(cells) >= 3:
                    procesos.append(
                        ProcesoJudicial(
                            numero_causa=cells[0].inner_text().strip() if len(cells) > 0 else "",
                            tipo=cells[1].inner_text().strip() if len(cells) > 1 else "",
                            estado=cells[2].inner_text().strip() if len(cells) > 2 else "",
                            fecha=cells[3].inner_text().strip() if len(cells) > 3 else "",
                            juzgado=cells[4].inner_text().strip() if len(cells) > 4 else "",
                            demandante=cells[5].inner_text().strip() if len(cells) > 5 else "",
                            demandado=cells[6].inner_text().strip() if len(cells) > 6 else "",
                        )
                    )
            except Exception:
                continue

        # Fallback: parse from body text if no table rows found
        if not procesos:
            lines = body_text.split("\n")
            for line in lines:
                stripped = line.strip()
                if stripped and any(
                    kw in stripped.lower() for kw in ["causa", "juicio", "proceso"]
                ):
                    if ":" in stripped:
                        procesos.append(
                            ProcesoJudicial(
                                numero_causa=stripped.split(":", 1)[1].strip(),
                            )
                        )

        return FuncionJudicialResult(
            queried_at=datetime.now(),
            documento=documento,
            procesos=procesos,
            total_procesos=len(procesos),
        )
