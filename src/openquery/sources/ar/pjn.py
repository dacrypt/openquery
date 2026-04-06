"""PJN source — Argentine federal judicial records (Poder Judicial de la Nacion).

Queries PJN for federal court case records by name or CUIT.

Flow:
1. Navigate to PJN search portal (SCW)
2. Enter nombre or CUIT
3. Submit and parse case list
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.pjn import CausaPjn, PjnResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

PJN_URL = "https://scw.pjn.gov.ar/scw/home.seam"


@register
class PjnSource(BaseSource):
    """Query Argentine federal judicial case records (PJN)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.pjn",
            display_name="PJN — Causas Judiciales Federales",
            description="Argentine federal judicial case records by name or CUIT",
            country="AR",
            url=PJN_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        nombre = input.extra.get("nombre", "")
        cuit = input.extra.get("cuit", "")
        consulta = nombre or cuit or input.document_number
        if not consulta:
            raise SourceError(
                "ar.pjn", "nombre or CUIT is required (pass via extra.nombre or extra.cuit)"
            )
        return self._query(consulta, is_cuit=bool(cuit), audit=input.audit)

    def _query(self, consulta: str, is_cuit: bool = False, audit: bool = False) -> PjnResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ar.pjn", "cuit" if is_cuit else "nombre", consulta)

        with browser.page(PJN_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill search field
                search_input = page.query_selector(
                    'input[name*="nombre"], input[name*="parte"], input[name*="busca"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("ar.pjn", "Could not find search input field")
                search_input.fill(consulta)
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
                raise SourceError("ar.pjn", f"Query failed: {e}") from e

    def _parse_result(self, page, consulta: str) -> PjnResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = PjnResult(queried_at=datetime.now(), consulta=consulta)

        # Parse case table rows
        rows = page.query_selector_all("table tr, .causas tr, .resultado tr")

        causas: list[CausaPjn] = []
        for row in rows[1:]:  # skip header
            cells = row.query_selector_all("td")
            if len(cells) >= 3:
                values = [(c.inner_text() or "").strip() for c in cells]
                causa = CausaPjn(
                    numero=values[0] if len(values) > 0 else "",
                    fuero=values[1] if len(values) > 1 else "",
                    juzgado=values[2] if len(values) > 2 else "",
                    caratula=values[3] if len(values) > 3 else "",
                    estado=values[4] if len(values) > 4 else "",
                    fecha=values[5] if len(values) > 5 else "",
                )
                causas.append(causa)

        result.causas = causas
        result.total_causas = len(causas)

        # Try to extract total from page text
        m = re.search(r"(\d+)\s*(?:causa|resultado|expediente)", body_text, re.IGNORECASE)
        if m:
            result.total_causas = max(result.total_causas, int(m.group(1)))

        return result
