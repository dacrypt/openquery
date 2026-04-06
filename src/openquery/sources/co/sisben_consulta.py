"""SISBEN Consulta source — Colombian social targeting system.

Queries the SISBEN (Sistema de Identificación de Potenciales
Beneficiarios de Programas Sociales) for social group and score.

Source: https://www.sisben.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.sisben_consulta import SisbenConsultaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SISBEN_URL = "https://www.sisben.gov.co/sisben/Paginas/Consulta-el-grupo.aspx"


@register
class SisbenConsultaSource(BaseSource):
    """Query SISBEN social targeting group and score."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.sisben_consulta",
            display_name="SISBEN — Consulta de Grupo",
            description="SISBEN social targeting system: group, subgroup, and beneficiary status",
            country="CO",
            url=SISBEN_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        documento = input.document_number.strip()
        if not documento:
            raise SourceError("co.sisben_consulta", "Document number (cédula) required")
        return self._query(documento, audit=input.audit)

    def _query(self, documento: str, audit: bool = False) -> SisbenConsultaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.sisben_consulta", "cedula", documento)

        with browser.page(SISBEN_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                doc_input = page.locator(
                    'input[name*="documento"], input[name*="cedula"], '
                    'input[id*="documento"], input[id*="cedula"], input[type="text"]'
                ).first
                if doc_input:
                    doc_input.fill(documento)
                    logger.info("Querying SISBEN for document: %s", documento[:4] + "***")

                    submit_btn = page.locator('button[type="submit"], input[type="submit"], button:has-text("Consultar")').first  # noqa: E501
                    if submit_btn:
                        submit_btn.click()
                    else:
                        doc_input.press("Enter")

                    page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, documento)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.sisben_consulta", f"Query failed: {e}") from e

    def _parse_result(self, page, documento: str) -> SisbenConsultaResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SisbenConsultaResult(queried_at=datetime.now(), documento=documento)

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nombre" in lower and ":" in stripped and not result.nombre:
                result.nombre = stripped.split(":", 1)[1].strip()
            elif "grupo" in lower and ":" in stripped and not result.grupo:
                result.grupo = stripped.split(":", 1)[1].strip()
            elif "subgrupo" in lower and ":" in stripped and not result.subgrupo:
                result.subgrupo = stripped.split(":", 1)[1].strip()

        return result
