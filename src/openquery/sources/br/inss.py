"""Brazil INSS source — social security contribution lookup.

Queries INSS portal (meu.inss.gov.br) for contribution status and benefit type by CPF.
Browser-based.

Source: https://meu.inss.gov.br/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.inss import InssResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

INSS_URL = "https://meu.inss.gov.br/"


@register
class InssSource(BaseSource):
    """Query Brazilian INSS portal for social security contribution status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.inss",
            display_name="INSS — Consulta de Contribuição (Meu INSS)",
            description="Brazilian INSS social security: contribution status and benefit type by CPF",  # noqa: E501
            country="BR",
            url=INSS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cpf = input.extra.get("cpf", "") or input.document_number
        if not cpf:
            raise SourceError("br.inss", "CPF is required (pass via extra.cpf or document_number)")
        cpf_clean = cpf.replace(".", "").replace("-", "").strip()
        return self._query(cpf_clean, audit=input.audit)

    def _query(self, cpf: str, audit: bool = False) -> InssResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("br.inss", "cpf", cpf)

        with browser.page(INSS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill CPF
                cpf_input = page.query_selector(
                    'input[name*="cpf" i], input[id*="cpf" i], '
                    'input[placeholder*="cpf" i], input[type="text"]'
                )
                if not cpf_input:
                    raise SourceError("br.inss", "Could not find CPF input field")

                cpf_input.fill(cpf)
                logger.info("Filled CPF: %s", cpf)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button:has-text("Entrar"), button:has-text("Consultar")'
                )
                if submit:
                    submit.click()
                else:
                    cpf_input.press("Enter")

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cpf)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("br.inss", f"Query failed: {e}") from e

    def _parse_result(self, page, cpf: str) -> InssResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = InssResult(queried_at=datetime.now(), cpf=cpf)
        details: dict[str, str] = {}

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue

            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val

            # Contribution status
            if any(k in lower for k in ("contribuição", "contribuicao", "situação", "situacao")):
                if ":" in stripped and not result.contribution_status:
                    result.contribution_status = stripped.split(":", 1)[1].strip()

            # Benefit type
            if any(k in lower for k in ("benefício", "beneficio", "tipo", "espécie", "especie")):
                if ":" in stripped and not result.benefit_type:
                    result.benefit_type = stripped.split(":", 1)[1].strip()

        result.details = details
        return result
