"""OAB source — Brazil lawyer verification.

Queries the OAB (Ordem dos Advogados do Brasil) for lawyer
registration status and details.

Source: https://www.oab.org.br/
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.oab import OabResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

OAB_URL = "https://www.oab.org.br/"
OAB_CONSULTA_URL = "https://cna.oab.org.br/"


@register
class OabSource(BaseSource):
    """Query Brazilian bar association (OAB) lawyer registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.oab",
            display_name="OAB — Cadastro Nacional de Advogados",
            description="OAB Brazilian lawyer registry: registration number, status, and state section",  # noqa: E501
            country="BR",
            url=OAB_CONSULTA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        oab_number = (
            input.extra.get("oab_number", "")
            or input.document_number
        ).strip()
        estado = input.extra.get("estado", "").strip()
        if not oab_number:
            raise SourceError("br.oab", "OAB number required (pass via extra.oab_number or document_number)")  # noqa: E501
        return self._query(oab_number, estado, audit=input.audit)

    def _query(self, oab_number: str, estado: str = "", audit: bool = False) -> OabResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("br.oab", "oab_number", oab_number)

        with browser.page(OAB_CONSULTA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                num_input = page.locator(
                    'input[name*="numero"], input[name*="inscricao"], '
                    'input[id*="numero"], input[placeholder*="número"], '
                    'input[type="text"]'
                ).first
                if num_input:
                    num_input.fill(oab_number)
                    logger.info("Querying OAB for number: %s", oab_number)

                    if estado:
                        estado_sel = page.locator('select[name*="uf"], select[name*="estado"], select[id*="uf"]').first  # noqa: E501
                        if estado_sel:
                            estado_sel.select_option(estado.upper())

                    submit_btn = page.locator('button[type="submit"], input[type="submit"], button:has-text("Pesquisar")').first  # noqa: E501
                    if submit_btn:
                        submit_btn.click()
                    else:
                        num_input.press("Enter")

                    page.wait_for_timeout(4000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, oab_number)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("br.oab", f"Query failed: {e}") from e

    def _parse_result(self, page, oab_number: str) -> OabResult:
        body_text = page.inner_text("body")
        result = OabResult(queried_at=datetime.now(), oab_number=oab_number)

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nome" in lower and ":" in stripped and not result.nome:
                result.nome = stripped.split(":", 1)[1].strip()
            elif ("uf" in lower or "estado" in lower or "seccional" in lower) and ":" in stripped and not result.estado:  # noqa: E501
                result.estado = stripped.split(":", 1)[1].strip()
            elif "situação" in lower and ":" in stripped and not result.status:
                result.status = stripped.split(":", 1)[1].strip()

        return result
