"""Poder Judicial source — Peruvian judicial case records (CEJ).

Queries the Consulta de Expedientes Judiciales for case records
by name or case number. Protected by image CAPTCHA.

Flow:
1. Navigate to CEJ search form
2. Enter search criteria (name or case number)
3. Submit search
4. Parse result table rows
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.poder_judicial import ExpedienteJudicial, PoderJudicialResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CEJ_URL = "https://cej.pj.gob.pe/cej/forms/busquedaform.html"


@register
class PoderJudicialSource(BaseSource):
    """Query Peruvian judicial case records (Poder Judicial CEJ)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.poder_judicial",
            display_name="Poder Judicial — Consulta de Expedientes",
            description="Peruvian judicial case records: cases, courts, status, and parties",
            country="PE",
            url=CEJ_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        nombre = input.extra.get("nombre", "")
        expediente = input.extra.get("expediente", "")
        if not nombre and not expediente:
            raise SourceError(
                "pe.poder_judicial",
                "Must provide extra.nombre or extra.expediente",
            )
        return self._query(nombre=nombre, expediente=expediente, audit=input.audit)

    def _query(
        self,
        nombre: str = "",
        expediente: str = "",
        audit: bool = False,
    ) -> PoderJudicialResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector(
                "pe.poder_judicial", "custom", nombre or expediente
            )

        with browser.page(CEJ_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_selector(
                    "input[type='text'], #txtNombre, #txtExpediente",
                    timeout=15000,
                )
                page.wait_for_timeout(2000)

                if nombre:
                    name_input = page.query_selector(
                        "#txtNombre, input[name*='nombre'], "
                        "input[name*='partes']"
                    )
                    if name_input:
                        name_input.fill(nombre)
                        logger.info("Filled nombre: %s", nombre)
                elif expediente:
                    exp_input = page.query_selector(
                        "#txtExpediente, input[name*='expediente'], "
                        "input[name*='numero']"
                    )
                    if exp_input:
                        exp_input.fill(expediente)
                        logger.info("Filled expediente: %s", expediente)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    "#btnBuscar, input[value='Buscar'], "
                    "button:has-text('Buscar'), button:has-text('Consultar')"
                )
                if submit:
                    submit.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector(
                    "table, .resultado, #divResultado, .grid",
                    timeout=15000,
                )

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page)

                if collector:
                    result.audit = collector.generate_pdf(
                        page, result.model_dump_json()
                    )

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError(
                    "pe.poder_judicial", f"Query failed: {e}"
                ) from e

    def _parse_result(self, page) -> PoderJudicialResult:
        """Parse the CEJ result page."""
        from datetime import datetime

        body_text = page.inner_text("body")
        result = PoderJudicialResult(queried_at=datetime.now())

        rows = page.query_selector_all("table tbody tr, table tr")
        expedientes: list[ExpedienteJudicial] = []

        for row in rows:
            cells = row.query_selector_all("td")
            if not cells or len(cells) < 3:
                continue
            values = [(c.inner_text() or "").strip() for c in cells]
            exp = ExpedienteJudicial(
                numero=values[0] if len(values) > 0 else "",
                juzgado=values[1] if len(values) > 1 else "",
                materia=values[2] if len(values) > 2 else "",
                estado=values[3] if len(values) > 3 else "",
                fecha=values[4] if len(values) > 4 else "",
                partes=values[5] if len(values) > 5 else "",
            )
            expedientes.append(exp)

        result.expedientes = expedientes
        result.total_expedientes = len(expedientes)

        # Fallback: try to extract total from text
        if not expedientes:
            m = re.search(r"(\d+)\s*(?:resultado|expediente)", body_text, re.IGNORECASE)
            if m:
                result.total_expedientes = int(m.group(1))

        return result
