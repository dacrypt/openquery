"""CAF Development Bank source — Latin America development data.

Queries the CAF (Development Bank of Latin America and the Caribbean)
data portal for development statistics.
Browser-based source (portal uses JavaScript rendering).

URL: https://www.caf.com/
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.caf import CafDataPoint, CafResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CAF_URL = "https://www.caf.com/"
CAF_DATA_URL = "https://www.caf.com/en/knowledge/data/"


@register
class CafSource(BaseSource):
    """Query CAF Development Bank Latin America data portal."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.caf",
            display_name="CAF — Development Bank of Latin America Data",
            description=(
                "CAF Development Bank data portal: infrastructure, social, "
                "and economic development data for Latin America"
            ),
            country="INTL",
            url=CAF_DATA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("search_term", input.document_number).strip()
        indicator = input.extra.get("indicator", "").strip()

        if not search_term:
            raise SourceError(
                "intl.caf",
                "Provide a search term (extra.search_term or document_number)",
            )

        return self._fetch(search_term, indicator)

    def _fetch(self, search_term: str, indicator: str) -> CafResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying CAF data portal: search_term=%s indicator=%s", search_term, indicator)  # noqa: E501

            data_points: list[CafDataPoint] = []
            details = ""

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(CAF_DATA_URL, wait_until="networkidle", timeout=self._timeout * 1000)

                # Search for the term
                search_input = page.query_selector("input[type='search'], input[type='text']")
                if search_input:
                    search_input.fill(search_term)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(2000)

                # Collect any visible data table rows
                rows = page.query_selector_all("table tr, .data-row")
                for row in rows[:20]:
                    cells = row.query_selector_all("td, .cell")
                    if len(cells) >= 2:
                        period = cells[0].inner_text().strip()
                        value = cells[1].inner_text().strip()
                        if period and value:
                            data_points.append(CafDataPoint(period=period, value=value))

                # Try to get the page title or heading as details
                heading = page.query_selector("h1, h2")
                if heading:
                    details = heading.inner_text().strip()[:200]

            return CafResult(
                queried_at=datetime.now(),
                search_term=search_term,
                indicator=indicator,
                data_points=data_points,
                details=details,
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.caf", f"Query failed: {e}") from e
