"""ANDE source — Paraguay electricity utility account status.

Queries the Administración Nacional de Electricidad (ANDE) for account status.

Source: https://www.ande.gov.py/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.py.ande import AndeResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ANDE_URL = "https://www.ande.gov.py/"


@register
class AndeSource(BaseSource):
    """Query Paraguay ANDE electricity account by account number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="py.ande",
            display_name="ANDE — Estado de Cuenta Eléctrica",
            description=(
                "Paraguay ANDE: electricity utility account status by account number"
            ),
            country="PY",
            url=ANDE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        account_number = input.extra.get("account", "") or input.document_number.strip()
        if not account_number:
            raise SourceError("py.ande", "Account number is required")
        return self._query(account_number=account_number, audit=input.audit)

    def _query(self, account_number: str, audit: bool = False) -> AndeResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("py.ande", "account", account_number)

        with browser.page(ANDE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[name*="cuenta"], input[id*="cuenta"], '
                    'input[name*="numero"], input[type="text"], '
                    'input[name*="suministro"], input[type="search"]'
                )
                if search_input:
                    search_input.fill(account_number)
                    logger.info("Querying ANDE for account: %s", account_number)

                    submit_btn = page.query_selector(
                        'button[type="submit"], input[type="submit"], '
                        'button:has-text("Consultar"), button:has-text("Buscar")'
                    )
                    if submit_btn:
                        submit_btn.click()
                    else:
                        search_input.press("Enter")

                    page.wait_for_timeout(4000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, account_number)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("py.ande", f"Query failed: {e}") from e

    def _parse_result(self, page, account_number: str) -> AndeResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        account_holder = ""
        account_status = ""
        balance = ""
        last_payment = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if any(kw in lower for kw in ["titular", "nombre", "cliente"]) and ":" in stripped and not account_holder:  # noqa: E501
                account_holder = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped and not account_status:
                account_status = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["saldo", "deuda", "monto"]) and ":" in stripped and not balance:  # noqa: E501
                balance = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["último pago", "pago"]) and ":" in stripped and not last_payment:  # noqa: E501
                last_payment = stripped.split(":", 1)[1].strip()

        return AndeResult(
            queried_at=datetime.now(),
            account_number=account_number,
            account_holder=account_holder,
            account_status=account_status,
            balance=balance,
            last_payment=last_payment,
            details=body_text.strip()[:500],
        )
