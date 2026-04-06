"""CFE electricity account source — Mexico.

Queries CFE for electricity account status by service number.

URL: https://www.cfe.mx/
Input: service number (custom)
Returns: account status, balance
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.cfe import CfeResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CFE_URL = "https://app.cfe.mx/Aplicaciones/CCFE/Resumenes/ResumenesB2C/Inicio.aspx"


@register
class CfeSource(BaseSource):
    """Query CFE electricity account status by service number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.cfe",
            display_name="CFE — Cuenta de Electricidad",
            description="Mexico CFE: electricity account status and balance lookup by service number",  # noqa: E501
            country="MX",
            url=CFE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        service_number = (input.extra.get("service_number", "") or input.document_number).strip()
        if not service_number:
            raise SourceError("mx.cfe", "Service number required (extra.service_number or document_number)")  # noqa: E501
        return self._fetch(service_number, audit=input.audit)

    def _fetch(self, service_number: str, audit: bool = False) -> CfeResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying CFE: service_number=%s", service_number)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(CFE_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[name*='servicio'], input[name*='numero'], input[type='text']"
                )
                if search_input:
                    search_input.fill(service_number)
                    submit = page.query_selector("button[type='submit'], input[type='submit']")
                    if submit:
                        submit.click()
                    else:
                        search_input.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                body_lower = body_text.lower()

                account_status = ""
                balance = ""

                for line in body_text.split("\n"):
                    stripped = line.strip()
                    lower = stripped.lower()
                    if "saldo" in lower and ":" in stripped and not balance:
                        balance = stripped.split(":", 1)[1].strip()
                    if "estado" in lower and ":" in stripped and not account_status:
                        account_status = stripped.split(":", 1)[1].strip()

                if not account_status:
                    if "al corriente" in body_lower or "pagado" in body_lower:
                        account_status = "Al corriente"
                    elif "adeudo" in body_lower or "vencido" in body_lower:
                        account_status = "Con adeudo"
                    elif "no encontr" in body_lower:
                        account_status = "No encontrado"
                    else:
                        account_status = "Consultado"

            return CfeResult(
                queried_at=datetime.now(),
                service_number=service_number,
                account_status=account_status,
                balance=balance,
                details=f"CFE query for service: {service_number}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("mx.cfe", f"Query failed: {e}") from e
