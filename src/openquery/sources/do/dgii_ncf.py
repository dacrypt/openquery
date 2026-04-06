"""DGII NCF source — Dominican Republic NCF invoice verification.

Queries Dominican Republic DGII (Dirección General de Impuestos Internos)
for NCF (Número de Comprobante Fiscal) validity by RNC + NCF.
Browser-based, no CAPTCHA.

URL: https://dgii.gov.do/app/WebApps/ConsultasWeb2/ConsultaNCF2/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.do.dgii_ncf import DoDgiiNcfResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DGII_NCF_URL = "https://dgii.gov.do/app/WebApps/ConsultasWeb2/ConsultaNCF2/"


@register
class DoDgiiNcfSource(BaseSource):
    """Query Dominican Republic DGII for NCF invoice validity."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="do.dgii_ncf",
            display_name="DGII — Consulta NCF (DO)",
            description="Dominican Republic DGII NCF invoice verification by RNC and NCF number",
            country="DO",
            url=DGII_NCF_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        rnc = input.extra.get("rnc", "") or input.document_number
        ncf = input.extra.get("ncf", "")
        if not rnc:
            raise SourceError("do.dgii_ncf", "RNC is required")
        if not ncf:
            raise SourceError("do.dgii_ncf", "NCF is required")
        return self._query(rnc.strip(), ncf.strip(), audit=input.audit)

    def _query(self, rnc: str, ncf: str, audit: bool = False) -> DoDgiiNcfResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("do.dgii_ncf", "rnc", rnc)

        with browser.page(DGII_NCF_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                rnc_input = page.query_selector(
                    "input[name*='rnc'], input[id*='rnc'], input[id*='RNC'], "
                    "input[placeholder*='RNC'], input[placeholder*='rnc']"
                )
                if not rnc_input:
                    raise SourceError("do.dgii_ncf", "Could not find RNC input field")

                rnc_input.fill(rnc)

                ncf_input = page.query_selector(
                    "input[name*='ncf'], input[id*='ncf'], input[id*='NCF'], "
                    "input[placeholder*='NCF'], input[placeholder*='ncf']"
                )
                if not ncf_input:
                    raise SourceError("do.dgii_ncf", "Could not find NCF input field")

                ncf_input.fill(ncf)
                logger.info("Querying DGII NCF for RNC: %s NCF: %s", rnc, ncf)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    "button[type='submit'], input[type='submit'], "
                    "button:has-text('Consultar'), button:has-text('Buscar'), "
                    "input[value*='Consultar']"
                )
                if submit:
                    submit.click()
                else:
                    ncf_input.press("Enter")

                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, rnc, ncf)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("do.dgii_ncf", f"Query failed: {e}") from e

    def _parse_result(self, page, rnc: str, ncf: str) -> DoDgiiNcfResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        lower_text = body_text.lower()

        valid_indicators = ["válido", "valido", "autorizado", "activo", "vigente"]
        invalid_indicators = ["no válido", "inválido", "invalido", "anulado", "cancelado"]

        ncf_valid = False
        for indicator in valid_indicators:
            if indicator in lower_text:
                ncf_valid = True
                break
        for indicator in invalid_indicators:
            if indicator in lower_text:
                ncf_valid = False
                break

        return DoDgiiNcfResult(
            queried_at=datetime.now(),
            rnc=rnc,
            ncf=ncf,
            ncf_valid=ncf_valid,
            details={"raw": body_text.strip()[:500]},
        )
