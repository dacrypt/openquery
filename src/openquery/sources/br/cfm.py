"""CFM source — Brazil doctor registry.

Queries the CFM (Conselho Federal de Medicina) for doctor
registration status and specialty information.

Source: https://portal.cfm.org.br/
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.cfm import CfmResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CFM_URL = "https://portal.cfm.org.br/"
CFM_CONSULTA_URL = "https://portal.cfm.org.br/busca-medicos/"


@register
class CfmSource(BaseSource):
    """Query Brazilian medical council (CFM) doctor registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.cfm",
            display_name="CFM — Registro de Médicos",
            description="CFM Brazilian doctor registry: CRM number, specialty, and registration status",  # noqa: E501
            country="BR",
            url=CFM_CONSULTA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        crm_number = (
            input.extra.get("crm_number", "")
            or input.document_number
        ).strip()
        if not crm_number:
            raise SourceError("br.cfm", "CRM number required (pass via extra.crm_number or document_number)")  # noqa: E501
        return self._query(crm_number, audit=input.audit)

    def _query(self, crm_number: str, audit: bool = False) -> CfmResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("br.cfm", "crm_number", crm_number)

        with browser.page(CFM_CONSULTA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                crm_input = page.locator(
                    'input[name*="crm"], input[name*="registro"], '
                    'input[id*="crm"], input[placeholder*="CRM"], '
                    'input[type="text"]'
                ).first
                if crm_input:
                    crm_input.fill(crm_number)
                    logger.info("Querying CFM for CRM: %s", crm_number)

                    submit_btn = page.locator('button[type="submit"], input[type="submit"], button:has-text("Pesquisar"), button:has-text("Buscar")').first  # noqa: E501
                    if submit_btn:
                        submit_btn.click()
                    else:
                        crm_input.press("Enter")

                    page.wait_for_timeout(4000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, crm_number)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("br.cfm", f"Query failed: {e}") from e

    def _parse_result(self, page, crm_number: str) -> CfmResult:
        body_text = page.inner_text("body")
        result = CfmResult(queried_at=datetime.now(), crm_number=crm_number)

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nome" in lower and ":" in stripped and not result.nome:
                result.nome = stripped.split(":", 1)[1].strip()
            elif "especialidade" in lower and ":" in stripped and not result.specialty:
                result.specialty = stripped.split(":", 1)[1].strip()
            elif "situação" in lower and ":" in stripped and not result.status:
                result.status = stripped.split(":", 1)[1].strip()

        return result
