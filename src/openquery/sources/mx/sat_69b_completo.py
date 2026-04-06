"""SAT 69-B Completo source — Mexican EFOS full list.

Queries the SAT (Servicio de Administracion Tributaria) 69-B full EFOS list
with detailed classification.

Flow:
1. Navigate to SAT EFOS list page
2. Enter RFC
3. Parse result for EFOS status and classification

Source: https://www.sat.gob.mx/consultas/76674/consulta-la-lista-de-contribuyentes-con-operaciones-presuntamente-inexistentes-
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.sat_69b_completo import Sat69bCompletoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SAT_69B_URL = "https://www.sat.gob.mx/consultas/76674/consulta-la-lista-de-contribuyentes-con-operaciones-presuntamente-inexistentes-"


@register
class Sat69bCompletoSource(BaseSource):
    """Query Mexican SAT 69-B full EFOS list."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.sat_69b_completo",
            display_name="SAT 69-B Completo — EFOS",
            description="Mexican SAT 69-B full EFOS list with classification",
            country="MX",
            url=SAT_69B_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        rfc = input.extra.get("rfc") or input.document_number
        if not rfc:
            raise SourceError("mx.sat_69b_completo", "rfc is required")
        return self._query(rfc, audit=input.audit)

    def _query(self, rfc: str, audit: bool = False) -> Sat69bCompletoResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("mx.sat_69b_completo", "custom", rfc)

        with browser.page(SAT_69B_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                rfc_input = page.query_selector(
                    'input[type="text"], input[id*="rfc"], '
                    'input[id*="RFC"], input[id*="buscar"]'
                )
                if not rfc_input:
                    raise SourceError("mx.sat_69b_completo", "Could not find RFC input field")

                rfc_input.fill(rfc)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="buscar"], button[id*="consultar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    rfc_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, rfc)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("mx.sat_69b_completo", f"Query failed: {e}") from e

    def _parse_result(self, page, rfc: str) -> Sat69bCompletoResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        taxpayer_name = ""
        efos_status = ""
        classification = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue
            if ("nombre" in lower or "razon" in lower or "contribuyente" in lower) and ":" in stripped:  # noqa: E501
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not taxpayer_name:
                    taxpayer_name = parts[1].strip()
            elif ("situacion" in lower or "estado" in lower or "efos" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not efos_status:
                    efos_status = parts[1].strip()
            elif ("clasificacion" in lower or "tipo" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not classification:
                    classification = parts[1].strip()

        is_efos = any(
            phrase in body_lower
            for phrase in ["efos", "presunta", "definitiva", "desvirtuado", "sentencia"]
        )

        no_results = any(
            phrase in body_lower
            for phrase in ["no se encontr", "no result", "sin resultados"]
        )

        if no_results:
            is_efos = False

        if not efos_status:
            efos_status = "Listado EFOS" if is_efos else "No encontrado"

        return Sat69bCompletoResult(
            queried_at=datetime.now(),
            rfc=rfc,
            taxpayer_name=taxpayer_name,
            efos_status=efos_status,
            classification=classification,
            details={"is_efos": is_efos},
        )
