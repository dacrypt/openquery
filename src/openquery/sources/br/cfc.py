"""CFC accountant registry source — Brazil.

Queries CFC (Conselho Federal de Contabilidade) for accountant status by CRC number.

URL: https://www.cfc.org.br/
Input: CRC number (custom)
Returns: accountant name, status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.cfc import CfcResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CFC_URL = "https://www.cfc.org.br/registro-profissional/pesquisa-de-profissional/"


@register
class CfcSource(BaseSource):
    """Query CFC accountant registry by CRC number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.cfc",
            display_name="CFC — Registro de Contadores",
            description="Brazil CFC accountant registry: CRC number and registration status lookup",
            country="BR",
            url=CFC_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        crc_number = (input.extra.get("crc_number", "") or input.document_number).strip()
        if not crc_number:
            raise SourceError("br.cfc", "CRC number required (extra.crc_number or document_number)")
        return self._query(crc_number, audit=input.audit)

    def _query(self, crc_number: str, audit: bool = False) -> CfcResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying CFC: crc=%s", crc_number)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(CFC_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[name*='crc'], input[name*='registro'], input[type='text']"
                )
                if search_input:
                    search_input.fill(crc_number)
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

            return CfcResult(
                queried_at=datetime.now(),
                crc_number=crc_number,
                nome=nome,
                status=status,
                details=f"CFC query for CRC: {crc_number}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("br.cfc", f"Query failed: {e}") from e
