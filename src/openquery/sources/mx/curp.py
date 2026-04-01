"""CURP source — Mexican population registry (RENAPO).

Queries the Mexican CURP validation system.
The portal uses a color CAPTCHA.

Flow:
1. Navigate to CURP consultation page
2. Enter CURP code
3. Solve color CAPTCHA
4. Submit and parse result
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.curp import CurpResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CURP_URL = "https://consultas.curp.gob.mx/CurpSP/gobmx/ConsultaCURP"


@register
class CurpSource(BaseSource):
    """Query Mexican CURP population registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.curp",
            display_name="CURP — Consulta de CURP",
            description="Mexican CURP validation: personal data and birth certificate status",
            country="MX",
            url=CURP_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        curp = input.extra.get("curp", "") or input.document_number
        if not curp:
            raise SourceError("mx.curp", "CURP is required (pass via extra.curp)")
        return self._query(curp, audit=input.audit)

    def _query(self, curp: str, audit: bool = False) -> CurpResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("mx.curp", "curp", curp)

        with browser.page(CURP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_selector('input[type="text"]', timeout=15000)
                page.wait_for_timeout(2000)

                # Fill CURP
                curp_input = page.query_selector(
                    'input[name*="curp"], input[name*="CURP"], input[id*="curp"], '
                    'input[type="text"]'
                )
                if not curp_input:
                    raise SourceError("mx.curp", "Could not find CURP input field")
                curp_input.fill(curp.upper())
                logger.info("Filled CURP: %s", curp)

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
                    curp_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, curp)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("mx.curp", f"Query failed: {e}") from e

    def _parse_result(self, page, curp: str) -> CurpResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        result = CurpResult(queried_at=datetime.now(), curp=curp.upper())

        # Parse fields from result page
        field_patterns = [
            (r"(?:nombre|names?)[:\s]+([^\n]+)", "nombre"),
            (r"(?:primer\s*apellido|apellido\s*paterno)[:\s]+([^\n]+)", "apellido_paterno"),
            (r"(?:segundo\s*apellido|apellido\s*materno)[:\s]+([^\n]+)", "apellido_materno"),
            (r"(?:fecha\s*(?:de\s*)?nacimiento)[:\s]+([^\n]+)", "fecha_nacimiento"),
            (r"(?:sexo|g[eé]nero)[:\s]+([^\n]+)", "sexo"),
            (r"(?:entidad\s*(?:de\s*)?nacimiento|estado\s*(?:de\s*)?nacimiento)[:\s]+([^\n]+)", "estado_nacimiento"),
            (r"(?:estatus|status)[:\s]+([^\n]+)", "estatus"),
            (r"(?:documento\s*probatorio)[:\s]+([^\n]+)", "documento_probatorio"),
        ]

        for pattern, field in field_patterns:
            m = re.search(pattern, body_text, re.IGNORECASE)
            if m:
                setattr(result, field, m.group(1).strip())

        # Try table-based parsing
        rows = page.query_selector_all("table tr, .datos-personales tr")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip().lower()
                value = (cells[1].inner_text() or "").strip()
                if "nombre" in label and not result.nombre:
                    result.nombre = value
                elif "paterno" in label:
                    result.apellido_paterno = value
                elif "materno" in label:
                    result.apellido_materno = value

        return result
