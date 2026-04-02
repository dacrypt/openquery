"""AFIP CUIT source — Argentine federal taxpayer registry.

Queries AFIP's public padron for taxpayer registration details by CUIT.

Flow:
1. Navigate to AFIP constancia page
2. Enter CUIT number
3. Submit and parse taxpayer details
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.afip_cuit import AfipCuitResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

AFIP_URL = "https://seti.afip.gob.ar/padron-puc-constancia-internet/ConsultaConstanciaAction.do"


@register
class AfipCuitSource(BaseSource):
    """Query Argentine AFIP taxpayer registry by CUIT."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.afip_cuit",
            display_name="AFIP — Constancia de CUIT",
            description="Argentine federal taxpayer registry: business name, activities, and tax regime",
            country="AR",
            url=AFIP_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cuit = input.extra.get("cuit", "") or input.document_number
        if not cuit:
            raise SourceError("ar.afip_cuit", "CUIT is required (pass via extra.cuit)")
        return self._query(cuit, audit=input.audit)

    def _query(self, cuit: str, audit: bool = False) -> AfipCuitResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("ar.afip_cuit", "cuit", cuit)

        with browser.page(AFIP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill CUIT
                cuit_input = page.query_selector(
                    'input[name*="cuit"], input[name*="CUIT"], input[id*="cuit"], '
                    'input[type="text"]'
                )
                if not cuit_input:
                    raise SourceError("ar.afip_cuit", "Could not find CUIT input field")
                cuit_input.fill(cuit)
                logger.info("Filled CUIT: %s", cuit)

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
                    cuit_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cuit)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ar.afip_cuit", f"Query failed: {e}") from e

    def _parse_result(self, page, cuit: str) -> AfipCuitResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        result = AfipCuitResult(queried_at=datetime.now(), cuit=cuit)

        # Parse fields
        field_patterns = [
            (r"(?:raz[oó]n\s*social|apellido\s*y\s*nombre|denominaci[oó]n)[:\s]+([^\n]+)", "razon_social"),
            (r"(?:tipo\s*(?:de\s*)?persona)[:\s]+([^\n]+)", "tipo_persona"),
            (r"(?:estado)[:\s]+([^\n]+)", "estado"),
            (r"(?:domicilio\s*fiscal)[:\s]+([^\n]+)", "domicilio_fiscal"),
            (r"(?:r[eé]gimen\s*(?:impositivo)?)[:\s]+([^\n]+)", "regimen_impositivo"),
            (r"(?:fecha\s*(?:de\s*)?contrato\s*social)[:\s]+([^\n]+)", "fecha_contrato_social"),
        ]

        for pattern, field in field_patterns:
            m = re.search(pattern, body_text, re.IGNORECASE)
            if m:
                setattr(result, field, m.group(1).strip())

        # Parse actividades
        actividades = re.findall(
            r"(?:actividad|actividades)[:\s]+([^\n]+)", body_text, re.IGNORECASE,
        )
        if actividades:
            result.actividades = [a.strip() for a in actividades]

        # Try table-based parsing
        rows = page.query_selector_all("table tr, .constancia tr")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip().lower()
                value = (cells[1].inner_text() or "").strip()
                if "razon social" in label or "denominacion" in label:
                    result.razon_social = result.razon_social or value
                elif "estado" in label and not result.estado:
                    result.estado = value
                elif "domicilio" in label and not result.domicilio_fiscal:
                    result.domicilio_fiscal = value

        return result
