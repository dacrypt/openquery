"""SUNAFIL source — Peruvian labor inspection records.

Queries SUNAFIL for labor inspection and sanction records by employer RUC.

Flow:
1. Navigate to SUNAFIL online consultations page
2. Enter RUC
3. Submit search
4. Parse inspection table
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.sunafil import SunafilInspeccion, SunafilResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUNAFIL_URL = "https://www.sunafil.gob.pe/consultas-en-linea.html"


@register
class SunafilSource(BaseSource):
    """Query Peruvian labor inspection registry (SUNAFIL)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.sunafil",
            display_name="SUNAFIL — Consulta de Inspecciones",
            description="Peruvian labor inspections and sanctions by employer RUC",
            country="PE",
            url=SUNAFIL_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        ruc = input.extra.get("ruc", "") or input.document_number or ""
        if not ruc:
            raise SourceError("pe.sunafil", "Must provide extra.ruc or document_number (RUC)")
        return self._query(ruc=ruc, audit=input.audit)

    def _query(self, ruc: str, audit: bool = False) -> SunafilResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("pe.sunafil", "custom", ruc)

        with browser.page(SUNAFIL_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                ruc_input = page.query_selector(
                    "input[name*='ruc' i], input[id*='ruc' i], "
                    "input[placeholder*='RUC' i], input[type='text']"
                )
                if ruc_input:
                    ruc_input.fill(ruc)
                    logger.info("Filled RUC: %s", ruc)
                else:
                    raise SourceError("pe.sunafil", "RUC input field not found")

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    "button[type='submit'], input[type='submit'], "
                    "button:has-text('Buscar'), button:has-text('Consultar'), "
                    "button:has-text('Consulta')"
                )
                if submit:
                    submit.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector(
                    "table, .resultado, #resultado, .list-group, .card",
                    timeout=15000,
                )

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, ruc)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pe.sunafil", f"Query failed: {e}") from e

    def _parse_result(self, page, ruc: str) -> SunafilResult:
        """Parse the SUNAFIL result page."""
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SunafilResult(queried_at=datetime.now(), ruc=ruc)

        # Extract employer name
        m = re.search(
            r"(?:Raz[oó]n Social|Empleador|Empresa)[:\s]+([^\n]+)",
            body_text, re.IGNORECASE,
        )
        if m:
            result.employer_name = m.group(1).strip()

        # Parse inspection table rows
        rows = page.query_selector_all("table tbody tr, table tr")
        inspections: list[SunafilInspeccion] = []
        sanctions: list[str] = []

        for row in rows:
            cells = row.query_selector_all("td")
            if not cells or len(cells) < 2:
                continue
            values = [(c.inner_text() or "").strip() for c in cells]
            inspeccion = SunafilInspeccion(
                numero=values[0] if len(values) > 0 else "",
                fecha=values[1] if len(values) > 1 else "",
                materia=values[2] if len(values) > 2 else "",
                resultado=values[3] if len(values) > 3 else "",
                sancion=values[4] if len(values) > 4 else "",
            )
            inspections.append(inspeccion)
            if inspeccion.sancion:
                sanctions.append(inspeccion.sancion)

        result.inspections = inspections
        result.inspections_count = len(inspections)
        result.sanctions = sanctions

        # Fallback count from text
        if not inspections:
            m2 = re.search(
                r"(\d+)\s*(?:inspecci[oó]n|resultado|registro)",
                body_text, re.IGNORECASE,
            )
            if m2:
                result.inspections_count = int(m2.group(1))

        return result
