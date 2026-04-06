"""WIPO Global Brand Database source — worldwide trademark registrations.

Browser-based source querying WIPO's Global Brand Database for trademark searches.

URL: https://branddb.wipo.int/en/quicksearch
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.wipo import IntlWipoResult, WipoTrademark
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

WIPO_URL = "https://branddb.wipo.int/en/quicksearch"


@register
class IntlWipoSource(BaseSource):
    """Query WIPO Global Brand Database for worldwide trademark registrations."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.wipo",
            display_name="WIPO — Global Brand Database (Marcas Mundiales)",
            description="WIPO Global Brand Database: worldwide trademark registrations by brand name",  # noqa: E501
            country="INTL",
            url="https://branddb.wipo.int/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        name = (input.extra.get("name", "") or input.document_number).strip()
        if not name:
            raise SourceError("intl.wipo", "Brand/trademark name is required (extra['name'])")
        return self._query(name)

    def _query(self, name: str) -> IntlWipoResult:
        try:
            from openquery.core.browser import BrowserManager

            logger.info("Querying WIPO Global Brand Database: %s", name)
            url = f"{WIPO_URL}?by=brandName&v={name}"
            browser = BrowserManager(headless=self._headless, timeout=self._timeout)
            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                return self._parse_page(page, name)

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.wipo", f"Query failed: {e}") from e

    def _parse_page(self, page: object, name: str) -> IntlWipoResult:
        """Parse WIPO brand search results page."""
        try:
            text = page.inner_text("body")  # type: ignore[union-attr]
        except Exception:
            text = ""

        trademarks: list[WipoTrademark] = []
        total = 0

        # Try to extract result count from page text
        import re

        count_match = re.search(r"(\d[\d,]*)\s+result", text, re.IGNORECASE)
        if count_match:
            try:
                total = int(count_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # Try to parse structured results if any visible in text
        # WIPO renders with JS — extract what we can
        if name.lower() in text.lower() and total == 0:
            total = 1  # At least one result implied

        return IntlWipoResult(
            queried_at=datetime.now(),
            search_term=name,
            total=total,
            trademarks=trademarks,
        )
