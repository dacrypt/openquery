"""CREA source — Brazil engineer registry.

Queries the CREA (Conselho Regional de Engenharia e Agronomia) for
engineer registration status and specialty information.

Source: https://www.crea-sp.org.br/
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.crea import CreaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CREA_URL = "https://www.crea-sp.org.br/"
CREA_CONSULTA_URL = "https://www.crea-sp.org.br/profissional/busca/"


@register
class CreaSource(BaseSource):
    """Query Brazilian engineering council (CREA) engineer registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.crea",
            display_name="CREA — Registro de Engenheiros",
            description="CREA Brazilian engineer registry: registration number, specialty, and status",  # noqa: E501
            country="BR",
            url=CREA_CONSULTA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        crea_number = (
            input.extra.get("crea_number", "")
            or input.document_number
        ).strip()
        if not crea_number:
            raise SourceError("br.crea", "CREA number required (pass via extra.crea_number or document_number)")  # noqa: E501
        return self._query(crea_number, audit=input.audit)

    def _query(self, crea_number: str, audit: bool = False) -> CreaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("br.crea", "crea_number", crea_number)

        with browser.page(CREA_CONSULTA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                crea_input = page.locator(
                    'input[name*="crea"], input[name*="registro"], '
                    'input[id*="crea"], input[placeholder*="CREA"], '
                    'input[type="text"]'
                ).first
                if crea_input:
                    crea_input.fill(crea_number)
                    logger.info("Querying CREA for number: %s", crea_number)

                    submit_btn = page.locator('button[type="submit"], input[type="submit"], button:has-text("Pesquisar"), button:has-text("Buscar")').first  # noqa: E501
                    if submit_btn:
                        submit_btn.click()
                    else:
                        crea_input.press("Enter")

                    page.wait_for_timeout(4000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, crea_number)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("br.crea", f"Query failed: {e}") from e

    def _parse_result(self, page, crea_number: str) -> CreaResult:
        body_text = page.inner_text("body")
        result = CreaResult(queried_at=datetime.now(), crea_number=crea_number)

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
