"""Brazil CPF source — Receita Federal citizen identity lookup.

Queries Brazil's Receita Federal for CPF (Cadastro de Pessoas Físicas)
status and registration data. Browser-based with CAPTCHA.

Source: https://servicos.receita.fazenda.gov.br/servicos/cpf/consultasituacao/consultapublica.asp
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.cpf import BrCpfResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CPF_URL = "https://servicos.receita.fazenda.gov.br/servicos/cpf/consultasituacao/consultapublica.asp"


@register
class BrCpfSource(BaseSource):
    """Query Brazilian citizen identity (CPF) from Receita Federal."""

    def __init__(self, timeout: float = 60.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.cpf",
            display_name="CPF — Cadastro de Pessoas Físicas",
            description="Brazilian citizen identity: CPF status, name, registration (Receita Federal)",
            country="BR",
            url=CPF_URL,
            supported_inputs=[DocumentType.SSN, DocumentType.CUSTOM],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=5,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cpf = input.extra.get("cpf", "") or input.document_number
        data_nascimento = input.extra.get("data_nascimento", "")
        if not cpf:
            raise SourceError("br.cpf", "CPF is required (11 digits)")
        cpf_clean = cpf.replace(".", "").replace("-", "").strip()
        return self._query(cpf_clean, data_nascimento, audit=input.audit)

    def _query(self, cpf: str, data_nascimento: str = "", audit: bool = False) -> BrCpfResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("br.cpf", "cpf", cpf)

        with browser.page(CPF_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                # Fill CPF
                cpf_input = page.query_selector(
                    '#txtCPF, input[name*="txtCPF"], input[id*="cpf" i], '
                    'input[type="text"]'
                )
                if not cpf_input:
                    raise SourceError("br.cpf", "Could not find CPF input field")

                cpf_input.fill(cpf)
                logger.info("Filled CPF: %s", cpf[:3] + "***")

                # Fill date of birth if provided
                if data_nascimento:
                    dob_input = page.query_selector(
                        '#txtDataNascimento, input[name*="DataNascimento"], '
                        'input[id*="nascimento" i]'
                    )
                    if dob_input:
                        dob_input.fill(data_nascimento)

                # Solve CAPTCHA using middleware
                from openquery.core.captcha_middleware import solve_page_captchas
                solve_page_captchas(page)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    '#id_submit, input[type="submit"], button[type="submit"], '
                    'input[value*="Consultar"]'
                )
                if submit:
                    submit.click()
                else:
                    cpf_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cpf)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("br.cpf", f"Query failed: {e}") from e

    def _parse_result(self, page, cpf: str) -> BrCpfResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = BrCpfResult(queried_at=datetime.now(), cpf=cpf)

        field_patterns = {
            "nome": "nome",
            "situação cadastral": "situacao_cadastral",
            "situacao cadastral": "situacao_cadastral",
            "data da inscrição": "data_inscricao",
            "data da inscricao": "data_inscricao",
            "dígito verificador": "digito_verificador",
            "digito verificador": "digito_verificador",
            "comprovante": "comprovante",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_patterns.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    setattr(result, field, value)
                    break

        return result
