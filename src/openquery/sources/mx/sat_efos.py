"""SAT EFOS source — Mexican phantom taxpayer blacklist (Art. 69-B CFF).

Queries the SAT portal for taxpayers listed under Article 69-B
(Empresas que Facturan Operaciones Simuladas — EFOS).

Flow:
1. Navigate to SAT 69-B search page
2. Enter RFC or nombre
3. Submit and parse result list
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.sat_efos import ContribuyenteEfos, SatEfosResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SAT_EFOS_URL = "https://listados.sat.gob.mx/"


@register
class SatEfosSource(BaseSource):
    """Query Mexican SAT 69-B phantom taxpayer blacklist (EFOS)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.sat_efos",
            display_name="SAT — Listado 69-B (EFOS)",
            description="Mexican SAT phantom taxpayer blacklist (EFOS): RFC, status, and DOF dates",
            country="MX",
            url=SAT_EFOS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        rfc = input.extra.get("rfc", "")
        nombre = input.extra.get("nombre", "")
        consulta = rfc or nombre or input.document_number
        if not consulta:
            raise SourceError("mx.sat_efos", "RFC or nombre is required (pass via extra.rfc or extra.nombre)")
        return self._query(consulta, is_rfc=bool(rfc), audit=input.audit)

    def _query(self, consulta: str, is_rfc: bool = True, audit: bool = False) -> SatEfosResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("mx.sat_efos", "rfc" if is_rfc else "nombre", consulta)

        with browser.page(SAT_EFOS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_selector('input[type="text"]', timeout=15000)
                page.wait_for_timeout(2000)

                # Fill search field
                search_input = page.query_selector(
                    'input[name*="rfc"], input[name*="nombre"], input[name*="busca"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("mx.sat_efos", "Could not find search input field")
                search_input.fill(consulta.upper() if is_rfc else consulta)
                logger.info("Filled search: %s", consulta)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    "button:has-text('Buscar'), button:has-text('Consultar')"
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, consulta)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("mx.sat_efos", f"Query failed: {e}") from e

    def _parse_result(self, page, consulta: str) -> SatEfosResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = SatEfosResult(queried_at=datetime.now(), consulta=consulta)

        # Parse result table rows
        rows = page.query_selector_all("table tr, .listado tr, .resultado tr")

        contribuyentes: list[ContribuyenteEfos] = []
        for row in rows[1:]:  # skip header
            cells = row.query_selector_all("td")
            if len(cells) >= 3:
                values = [(c.inner_text() or "").strip() for c in cells]
                contrib = ContribuyenteEfos(
                    rfc=values[0] if len(values) > 0 else "",
                    nombre=values[1] if len(values) > 1 else "",
                    situacion=values[2] if len(values) > 2 else "",
                    fecha_publicacion_dof=values[3] if len(values) > 3 else "",
                    fecha_publicacion_sat=values[4] if len(values) > 4 else "",
                )
                contribuyentes.append(contrib)

        result.contribuyentes = contribuyentes
        result.total_resultados = len(contribuyentes)

        # Try to extract total from page text
        m = re.search(r"(\d+)\s*(?:resultado|registro|contribuyente)", body_text, re.IGNORECASE)
        if m:
            result.total_resultados = max(result.total_resultados, int(m.group(1)))

        return result
