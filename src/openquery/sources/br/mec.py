"""MEC university accreditation source — Brazil.

Queries e-MEC for institution accreditation status.

URL: https://emec.mec.gov.br/
Input: institution name (custom)
Returns: accreditation status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.mec import MecResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MEC_URL = "https://emec.mec.gov.br/emec/consulta-cadastro/detalhamento/d96957f455f6405d14c6542552b0f6eb"


@register
class MecSource(BaseSource):
    """Query Brazil MEC (e-MEC) university accreditation."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.mec",
            display_name="MEC — e-MEC Credenciamento de IES",
            description="Brazil MEC university and institution accreditation via e-MEC portal",
            country="BR",
            url=MEC_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("institution_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "br.mec",
                "Provide an institution name (extra.institution_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> MecResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying MEC e-MEC: search_term=%s", search_term)

            search_url = (
                "https://emec.mec.gov.br/emec/consulta-cadastro/consulta-ies/"
                "d96957f455f6405d14c6542552b0f6eb"
            )

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(search_url, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[name*='nome'], input[id*='nome'], input[type='text']"
                )
                if search_input:
                    search_input.fill(search_term)
                    submit = page.query_selector("button[type='submit'], input[type='submit']")
                    if submit:
                        submit.click()
                    else:
                        search_input.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                body_lower = body_text.lower()
                search_lower = search_term.lower()

                institution_name = ""
                accreditation_status = ""

                found = search_lower in body_lower
                if found:
                    for line in body_text.split("\n"):
                        if search_term.lower() in line.lower():
                            institution_name = line.strip()
                            break
                    if "credenciad" in body_lower:
                        accreditation_status = "Credenciada"
                    elif "descredenciad" in body_lower:
                        accreditation_status = "Descredenciada"
                    else:
                        accreditation_status = "Encontrada"
                else:
                    accreditation_status = "Não encontrada"

            return MecResult(
                queried_at=datetime.now(),
                search_term=search_term,
                institution_name=institution_name,
                accreditation_status=accreditation_status,
                details=f"e-MEC query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("br.mec", f"Query failed: {e}") from e
