"""PJUD source — Chilean judicial records (Oficina Judicial Virtual).

Queries the Chilean judiciary for case records by RUT or name.
The portal uses reCAPTCHA.

Flow:
1. Navigate to PJUD virtual office
2. Enter RUT or nombre
3. Solve reCAPTCHA
4. Submit and parse case list
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.pjud import CausaJudicial, PjudResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

PJUD_URL = "https://oficinajudicialvirtual.pjud.cl/"


@register
class PjudSource(BaseSource):
    """Query Chilean judicial case records (PJUD)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.pjud",
            display_name="PJUD — Causas Judiciales",
            description="Chilean judicial case records by RUT or name",
            country="CL",
            url=PJUD_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        consulta = input.document_number.strip()
        is_rut = input.document_type == DocumentType.RUT
        return self._query(consulta, is_rut=is_rut, audit=input.audit)

    def _query(self, consulta: str, is_rut: bool = True, audit: bool = False) -> PjudResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cl.pjud", "rut" if is_rut else "nombre", consulta)

        with browser.page(PJUD_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill search field
                search_input = page.query_selector(
                    'input[name*="rut"], input[name*="nombre"], input[type="text"]'
                )
                if not search_input:
                    raise SourceError("cl.pjud", "Could not find search input field")
                search_input.fill(consulta)
                logger.info("Filled search field: %s", consulta)

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
                raise SourceError("cl.pjud", f"Query failed: {e}") from e

    def _parse_result(self, page, consulta: str) -> PjudResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = PjudResult(queried_at=datetime.now(), consulta=consulta)

        # Parse case table rows
        rows = page.query_selector_all("table tr, .tabla-causas tr, .resultado tr")

        causas: list[CausaJudicial] = []
        for row in rows[1:]:  # skip header
            cells = row.query_selector_all("td")
            if len(cells) >= 4:
                values = [(c.inner_text() or "").strip() for c in cells]
                causa = CausaJudicial(
                    rol=values[0] if len(values) > 0 else "",
                    tribunal=values[1] if len(values) > 1 else "",
                    materia=values[2] if len(values) > 2 else "",
                    estado=values[3] if len(values) > 3 else "",
                    fecha=values[4] if len(values) > 4 else "",
                    caratulado=values[5] if len(values) > 5 else "",
                )
                causas.append(causa)

        result.causas = causas
        result.total_causas = len(causas)

        # Try to extract total from page text
        m = re.search(r"(\d+)\s*(?:causa|resultado|registro)", body_text, re.IGNORECASE)
        if m:
            result.total_causas = max(result.total_causas, int(m.group(1)))

        return result
