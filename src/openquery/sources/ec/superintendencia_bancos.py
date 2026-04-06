"""Ecuador Superintendencia de Bancos source.

Queries Superintendencia de Bancos for supervised financial entities by RUC.

URL: https://www.superbancos.gob.ec/
Input: RUC
Returns: entity name, type, financial data
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ec.superintendencia_bancos import EcSuperintendenciaBancosResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUPERBANCOS_URL = "https://www.superbancos.gob.ec/bancos/index.php/component/k2/itemlist/category/102"


@register
class EcSuperintendenciaBancosSource(BaseSource):
    """Query Ecuador Superintendencia de Bancos for supervised entity data."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ec.superintendencia_bancos",
            display_name="Superintendencia de Bancos Ecuador — Entidades Supervisadas",
            description="Ecuador Superintendencia de Bancos: supervised financial entity lookup by RUC",  # noqa: E501
            country="EC",
            url=SUPERBANCOS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        ruc = (input.extra.get("ruc", "") or input.document_number).strip()
        if not ruc:
            raise SourceError(
                "ec.superintendencia_bancos",
                "RUC required (extra.ruc or document_number)",
            )
        return self._fetch(ruc, audit=input.audit)

    def _fetch(self, ruc: str, audit: bool = False) -> EcSuperintendenciaBancosResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying Superbancos Ecuador: ruc=%s", ruc)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(SUPERBANCOS_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)  # noqa: E501
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[type='search'], input[type='text'], input[name*='ruc']"
                )
                if search_input:
                    search_input.fill(ruc)
                    submit = page.query_selector("button[type='submit'], input[type='submit']")
                    if submit:
                        submit.click()
                    else:
                        search_input.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                body_text.lower()

                entity_name = ""
                entity_type = ""
                financial_data = ""

                for line in body_text.split("\n"):
                    stripped = line.strip()
                    lower = stripped.lower()
                    if ruc in stripped and not entity_name:
                        entity_name = stripped
                    if ("tipo" in lower or "entidad" in lower) and ":" in stripped and not entity_type:  # noqa: E501
                        entity_type = stripped.split(":", 1)[1].strip()
                    if ("capital" in lower or "activos" in lower) and ":" in stripped and not financial_data:  # noqa: E501
                        financial_data = stripped.split(":", 1)[1].strip()

            return EcSuperintendenciaBancosResult(
                queried_at=datetime.now(),
                ruc=ruc,
                entity_name=entity_name,
                entity_type=entity_type,
                financial_data=financial_data,
                details=f"Superbancos Ecuador query for RUC: {ruc}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("ec.superintendencia_bancos", f"Query failed: {e}") from e
