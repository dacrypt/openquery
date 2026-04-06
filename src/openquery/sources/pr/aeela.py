"""Puerto Rico LUMA/AEE electric utility source — account status lookup.

Queries LUMA Energy (formerly AEE) portal for electric account status and balance.
Browser-based.

Source: https://lumapr.com/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pr.aeela import AeelaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

AEELA_URL = "https://lumapr.com/pay-my-bill/"


@register
class AeelaSource(BaseSource):
    """Query LUMA/AEE Puerto Rico electric utility for account status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pr.aeela",
            display_name="LUMA/AEE — Cuenta Eléctrica (Puerto Rico)",
            description="Puerto Rico LUMA/AEE electric utility: account status and balance by account number",  # noqa: E501
            country="PR",
            url=AEELA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        account_number = input.extra.get("account_number", "") or input.document_number
        if not account_number:
            raise SourceError(
                "pr.aeela",
                "Account number is required (pass via extra.account_number or document_number)",
            )
        return self._query(account_number.strip(), audit=input.audit)

    def _query(self, account_number: str, audit: bool = False) -> AeelaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pr.aeela", "account_number", account_number)

        with browser.page(AEELA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                account_input = page.query_selector(
                    'input[name*="account" i], input[id*="account" i], '
                    'input[name*="cuenta" i], input[id*="cuenta" i], '
                    'input[placeholder*="account" i], input[placeholder*="cuenta" i], '
                    'input[type="text"]'
                )
                if not account_input:
                    raise SourceError("pr.aeela", "Could not find account number input field")
                account_input.fill(account_number)
                logger.info("Filled account number: %s", account_number)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    "button:has-text('Search'), button:has-text('Buscar'), "
                    "button:has-text('Continue'), button:has-text('Continuar')"
                )
                if submit:
                    submit.click()
                else:
                    account_input.press("Enter")

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, account_number)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pr.aeela", f"Query failed: {e}") from e

    def _parse_result(self, page, account_number: str) -> AeelaResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = AeelaResult(queried_at=datetime.now(), account_number=account_number)
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

            # Account status
            if any(k in lower for k in ("status", "estado", "account status", "cuenta")):
                if ":" in stripped and not result.account_status:
                    result.account_status = stripped.split(":", 1)[1].strip()

            # Balance
            if any(k in lower for k in ("balance", "amount due", "total", "balance owed")):
                if ":" in stripped and not result.balance:
                    result.balance = stripped.split(":", 1)[1].strip()
                elif "$" in stripped and not result.balance:
                    result.balance = stripped

        result.details = details
        return result
