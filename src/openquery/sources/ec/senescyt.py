"""SENESCYT source — Ecuador professional degree verification.

Queries Ecuador's SENESCYT for professional degree/title verification
by cedula or surname.

Flow:
1. Navigate to the SENESCYT consultation page
2. Enter cedula or surname
3. Submit and parse results

Source: https://www.senescyt.gob.ec/web/guest/consultas
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ec.senescyt import SenescytResult, TituloProfesional
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SENESCYT_URL = "https://www.senescyt.gob.ec/web/guest/consultas"


@register
class SenescytSource(BaseSource):
    """Query Ecuador professional degree verification from SENESCYT."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ec.senescyt",
            display_name="SENESCYT — Titulos Profesionales",
            description="Ecuador professional degree verification from SENESCYT",
            country="EC",
            url=SENESCYT_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in (DocumentType.CEDULA, DocumentType.CUSTOM):
            raise SourceError("ec.senescyt", f"Unsupported input type: {input.document_type}")

        documento = input.document_number.strip()
        apellidos = input.extra.get("apellidos", "").strip()

        if not documento and not apellidos:
            raise SourceError(
                "ec.senescyt",
                "Must provide document_number (cedula) or extra['apellidos']",
            )

        return self._query(documento, apellidos=apellidos, audit=input.audit)

    def _query(self, documento: str, apellidos: str = "", audit: bool = False) -> SenescytResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None
        search_term = documento or apellidos

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ec.senescyt", "cedula", search_term)

        with browser.page(SENESCYT_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill search field
                if documento:
                    doc_input = page.query_selector(
                        'input[id*="cedula"], input[id*="identificacion"], '
                        'input[name*="cedula"], input[type="text"]'
                    )
                    if doc_input:
                        doc_input.fill(documento)
                elif apellidos:
                    name_input = page.query_selector(
                        'input[id*="apellido"], input[id*="nombre"], '
                        'input[name*="apellido"], input[type="text"]'
                    )
                    if name_input:
                        name_input.fill(apellidos)

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

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ec.senescyt", f"Query failed: {e}") from e

    def _parse_result(self, page, documento: str) -> SenescytResult:
        from datetime import datetime

        titulos: list[TituloProfesional] = []

        # Try to find table rows with degree data
        rows = page.query_selector_all("table tbody tr, .resultado-fila, .titulo-item")
        for row in rows:
            try:
                cells = row.query_selector_all("td, .campo")
                if len(cells) >= 2:
                    titulos.append(
                        TituloProfesional(
                            titulo=cells[0].inner_text().strip() if len(cells) > 0 else "",
                            institucion=cells[1].inner_text().strip() if len(cells) > 1 else "",
                            tipo=cells[2].inner_text().strip() if len(cells) > 2 else "",
                            nivel=cells[3].inner_text().strip() if len(cells) > 3 else "",
                            fecha_registro=cells[4].inner_text().strip() if len(cells) > 4 else "",
                            numero_registro=cells[5].inner_text().strip() if len(cells) > 5 else "",
                        )
                    )
            except Exception:
                continue

        # Fallback: parse from body text
        if not titulos:
            body_text = page.inner_text("body")
            lines = body_text.split("\n")
            titulo_current: dict[str, str] = {}
            for line in lines:
                stripped = line.strip()
                lower = stripped.lower()
                if ("t\u00edtulo" in lower or "titulo" in lower) and ":" in stripped:
                    if titulo_current.get("titulo"):
                        titulos.append(TituloProfesional(**titulo_current))
                        titulo_current = {}
                    titulo_current["titulo"] = stripped.split(":", 1)[1].strip()
                elif ("instituci" in lower or "universidad" in lower) and ":" in stripped:
                    titulo_current["institucion"] = stripped.split(":", 1)[1].strip()
                elif "tipo" in lower and ":" in stripped:
                    titulo_current["tipo"] = stripped.split(":", 1)[1].strip()
                elif "nivel" in lower and ":" in stripped:
                    titulo_current["nivel"] = stripped.split(":", 1)[1].strip()
                elif "registro" in lower and "fecha" in lower and ":" in stripped:
                    titulo_current["fecha_registro"] = stripped.split(":", 1)[1].strip()
                elif (
                    ("n\u00famero" in lower or "numero" in lower)
                    and "registro" in lower
                    and ":" in stripped
                ):
                    titulo_current["numero_registro"] = stripped.split(":", 1)[1].strip()
            if titulo_current.get("titulo"):
                titulos.append(TituloProfesional(**titulo_current))

        return SenescytResult(
            queried_at=datetime.now(),
            documento=documento,
            titulos=titulos,
            total_titulos=len(titulos),
        )
