"""INFONAVIT housing credit source — Mexico.

Queries INFONAVIT for housing credit status by NSS.

URL: https://portalmx.infonavit.org.mx/
Input: NSS (Número de Seguridad Social)
Returns: credit status, balance
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.infonavit import InfonavitResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

INFONAVIT_URL = "https://portalmx.infonavit.org.mx/wps/portal/infonavit-web/trabajadores/para-tu-credito/consulta-tu-saldo/"


@register
class InfonavitSource(BaseSource):
    """Query INFONAVIT housing credit status by NSS."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.infonavit",
            display_name="INFONAVIT — Crédito de Vivienda",
            description="Mexico INFONAVIT: housing credit status and balance lookup by NSS",
            country="MX",
            url=INFONAVIT_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        nss = (input.extra.get("nss", "") or input.document_number).strip()
        if not nss:
            raise SourceError("mx.infonavit", "NSS required (extra.nss or document_number)")
        return self._fetch(nss, audit=input.audit)

    def _fetch(self, nss: str, audit: bool = False) -> InfonavitResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying INFONAVIT: nss=%s", nss)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(INFONAVIT_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)  # noqa: E501
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[name*='nss'], input[name*='seguridad'], input[type='text']"
                )
                if search_input:
                    search_input.fill(nss)
                    submit = page.query_selector("button[type='submit'], input[type='submit']")
                    if submit:
                        submit.click()
                    else:
                        search_input.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                body_lower = body_text.lower()

                credit_status = ""
                balance = ""

                for line in body_text.split("\n"):
                    stripped = line.strip()
                    lower = stripped.lower()
                    if ("crédito" in lower or "credito" in lower) and ":" in stripped and not credit_status:  # noqa: E501
                        credit_status = stripped.split(":", 1)[1].strip()
                    if "saldo" in lower and ":" in stripped and not balance:
                        balance = stripped.split(":", 1)[1].strip()

                if not credit_status:
                    if "activo" in body_lower or "vigente" in body_lower:
                        credit_status = "Activo"
                    elif "liquidado" in body_lower:
                        credit_status = "Liquidado"
                    elif "no encontr" in body_lower:
                        credit_status = "No encontrado"
                    else:
                        credit_status = "Consultado"

            return InfonavitResult(
                queried_at=datetime.now(),
                nss=nss,
                credit_status=credit_status,
                balance=balance,
                details=f"INFONAVIT query for NSS: {nss}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("mx.infonavit", f"Query failed: {e}") from e
