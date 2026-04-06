"""CONFEF physical education professional source — Brazil.

Queries CONFEF for physical education professional status by CREF number.

URL: https://www.confef.org.br/
Input: CREF number (custom)
Returns: professional name, status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.confef import ConfefResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CONFEF_URL = "https://www.confef.org.br/confef/comunicacao/registros-no-confef"


@register
class ConfefSource(BaseSource):
    """Query CONFEF physical education professional registry by CREF number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.confef",
            display_name="CONFEF — Registro de Profissionais de Educação Física",
            description="Brazil CONFEF physical education professional registry: CREF number and status lookup",  # noqa: E501
            country="BR",
            url=CONFEF_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cref_number = (input.extra.get("cref_number", "") or input.document_number).strip()
        if not cref_number:
            raise SourceError("br.confef", "CREF number required (extra.cref_number or document_number)")  # noqa: E501
        return self._query(cref_number, audit=input.audit)

    def _query(self, cref_number: str, audit: bool = False) -> ConfefResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying CONFEF: cref=%s", cref_number)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(CONFEF_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[name*='cref'], input[name*='registro'], input[type='text']"
                )
                if search_input:
                    search_input.fill(cref_number)
                    submit = page.query_selector("button[type='submit'], input[type='submit']")
                    if submit:
                        submit.click()
                    else:
                        search_input.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                body_lower = body_text.lower()

                nome = ""
                status = ""

                for line in body_text.split("\n"):
                    stripped = line.strip()
                    lower = stripped.lower()
                    if "nome" in lower and ":" in stripped and not nome:
                        nome = stripped.split(":", 1)[1].strip()
                    if ("situação" in lower or "status" in lower) and ":" in stripped and not status:  # noqa: E501
                        status = stripped.split(":", 1)[1].strip()

                if not status:
                    if "ativo" in body_lower or "regular" in body_lower:
                        status = "Ativo"
                    elif "cancelado" in body_lower or "suspenso" in body_lower:
                        status = "Cancelado/Suspenso"
                    elif "não encontr" in body_lower or "nenhum" in body_lower:
                        status = "Não encontrado"

            return ConfefResult(
                queried_at=datetime.now(),
                cref_number=cref_number,
                nome=nome,
                status=status,
                details=f"CONFEF query for CREF: {cref_number}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("br.confef", f"Query failed: {e}") from e
