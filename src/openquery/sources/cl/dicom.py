"""Chile DICOM source — Equifax credit report public summary.

Queries Equifax Chile public portal for DICOM credit status by RUT.
Browser-based.

Source: https://www.equifax.cl/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.dicom import DicomResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DICOM_URL = "https://www.equifax.cl/personas/consulta-dicom/"


@register
class DicomSource(BaseSource):
    """Query Equifax Chile public portal for DICOM credit status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.dicom",
            display_name="DICOM — Consulta de Crédito Equifax Chile",
            description="Chile DICOM/Equifax credit report public summary: clean or delinquent status by RUT",  # noqa: E501
            country="CL",
            url=DICOM_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        rut = input.extra.get("rut", "") or input.document_number
        if not rut:
            raise SourceError("cl.dicom", "RUT is required (pass via extra.rut)")
        return self._query(rut.strip(), audit=input.audit)

    def _query(self, rut: str, audit: bool = False) -> DicomResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cl.dicom", "rut", rut)

        with browser.page(DICOM_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                rut_input = page.query_selector(
                    'input[name*="rut" i], input[id*="rut" i], '
                    'input[placeholder*="rut" i], input[type="text"]'
                )
                if not rut_input:
                    raise SourceError("cl.dicom", "Could not find RUT input field")
                rut_input.fill(rut)
                logger.info("Filled RUT: %s", rut)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    "button:has-text('Consultar'), button:has-text('Buscar')"
                )
                if submit:
                    submit.click()
                else:
                    rut_input.press("Enter")

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, rut)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("cl.dicom", f"Query failed: {e}") from e

    def _parse_result(self, page, rut: str) -> DicomResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        lower_body = body_text.lower()
        result = DicomResult(queried_at=datetime.now(), rut=rut)
        details: dict[str, str] = {}

        # Determine DICOM status
        if any(k in lower_body for k in ("sin deudas", "sin dicom", "limpio", "no registra")):
            result.dicom_status = "Sin DICOM"
        elif any(k in lower_body for k in ("con dicom", "deuda", "moroso", "protesto")):
            result.dicom_status = "Con DICOM"

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val
                    lower_key = key.lower()
                    if any(k in lower_key for k in ("estado", "situación", "situacion", "dicom")):
                        if not result.dicom_status:
                            result.dicom_status = val

        result.details = details
        return result
