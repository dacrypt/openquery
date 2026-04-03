"""OSCE Sancionados source — Peruvian sanctioned government suppliers.

Queries OSCE for suppliers sanctioned/disqualified from government contracting.

Flow:
1. Navigate to OSCE inhabilitados page
2. Enter RUC or supplier name
3. Submit search
4. Parse result table rows
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.osce_sancionados import OsceSancionadosResult, ProveedorSancionado
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

OSCE_URL = "https://www.rnp.gob.pe/consultasenlinea/inhabilitados/busqueda.asp"


@register
class OsceSancionadosSource(BaseSource):
    """Query Peruvian sanctioned supplier registry (OSCE)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.osce_sancionados",
            display_name="OSCE — Proveedores Sancionados",
            description="Peruvian sanctioned government suppliers: disqualifications and sanctions",
            country="PE",
            url=OSCE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        ruc = input.extra.get("ruc", "")
        name = input.extra.get("name", "")
        if not ruc and not name:
            raise SourceError(
                "pe.osce_sancionados",
                "Must provide extra.ruc or extra.name",
            )
        return self._query(ruc=ruc, name=name, audit=input.audit)

    def _query(
        self,
        ruc: str = "",
        name: str = "",
        audit: bool = False,
    ) -> OsceSancionadosResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector(
                "pe.osce_sancionados", "custom", ruc or name
            )

        with browser.page(OSCE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill RUC or name — exact IDs from rnp.gob.pe
                if ruc:
                    ruc_input = page.query_selector('#ruc, input[name="ruc"]')
                    if ruc_input:
                        ruc_input.fill(ruc)
                        logger.info("Filled RUC: %s", ruc)
                elif name:
                    name_input = page.query_selector('#rz, input[name="rz"]')
                    if name_input:
                        name_input.fill(name)
                        logger.info("Filled name: %s", name)

                # Solve image CAPTCHA using universal middleware (LLM vision chain)
                from openquery.core.captcha_middleware import solve_page_captchas
                solve_page_captchas(page)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit — use the appropriate button
                submit = page.query_selector(
                    'button.btn-warning, '
                    'input[type="submit"]'
                )
                if submit:
                    submit.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector(
                    "table, .resultado, #divResultado, .list-group",
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
                    "pe.osce_sancionados", f"Query failed: {e}"
                ) from e

    def _parse_result(self, page) -> OsceSancionadosResult:
        """Parse the OSCE result page."""
        from datetime import datetime

        body_text = page.inner_text("body")
        result = OsceSancionadosResult(queried_at=datetime.now())

        rows = page.query_selector_all("table tbody tr, table tr")
        sancionados: list[ProveedorSancionado] = []

        for row in rows:
            cells = row.query_selector_all("td")
            if not cells or len(cells) < 3:
                continue
            values = [(c.inner_text() or "").strip() for c in cells]
            sancionado = ProveedorSancionado(
                nombre=values[0] if len(values) > 0 else "",
                ruc=values[1] if len(values) > 1 else "",
                sancion=values[2] if len(values) > 2 else "",
                fecha_inicio=values[3] if len(values) > 3 else "",
                fecha_fin=values[4] if len(values) > 4 else "",
                motivo=values[5] if len(values) > 5 else "",
                estado=values[6] if len(values) > 6 else "",
            )
            sancionados.append(sancionado)

        result.sancionados = sancionados
        result.total_sancionados = len(sancionados)

        # Fallback: extract count from text
        if not sancionados:
            m = re.search(
                r"(\d+)\s*(?:resultado|registro|sancion)", body_text, re.IGNORECASE
            )
            if m:
                result.total_sancionados = int(m.group(1))

        return result
