"""ILO labor statistics source.

Queries the ILO STAT API for labor statistics.
Free REST API, no auth, no CAPTCHA.

API: https://www.ilo.org/ilostat-files/WEB_bulk_download/indicator/
Docs: https://ilostat.ilo.org/resources/ilostat-developer-tools/
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.ilo import IloDataPoint, IloResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ILO_URL = "https://ilostat.ilo.org/"
ILO_API_URL = "https://www.ilo.org/sdmx/rest/data/ILO,{indicator},1.0/{country}"


@register
class IloSource(BaseSource):
    """Query ILO labor statistics by country and indicator."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.ilo",
            display_name="ILO — International Labour Statistics (ILOSTAT)",
            description="ILO ILOSTAT labor statistics by country and indicator",
            country="INTL",
            url=ILO_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        country = input.extra.get("country", input.document_number).strip().upper()
        indicator = input.extra.get("indicator", "").strip()

        if not country:
            raise SourceError(
                "intl.ilo",
                "Provide a country ISO2 code (extra.country or document_number)",
            )
        if not indicator:
            raise SourceError(
                "intl.ilo",
                "Provide an indicator code (extra.indicator), e.g. UNE_TUNE_SEX_AGE_NB",
            )

        return self._fetch(country, indicator)

    def _fetch(self, country: str, indicator: str) -> IloResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying ILO: country=%s indicator=%s", country, indicator)

            search_url = (
                f"{ILO_URL}data/?indicator={indicator}&ref_area={country}"
            )

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(search_url, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                page.inner_text("body")

                data_points: list[IloDataPoint] = []

                # Parse any table rows with period/value pairs
                rows = page.query_selector_all("table tbody tr")
                for row in rows[:20]:
                    cells = row.query_selector_all("td")
                    if len(cells) >= 2:
                        period = cells[0].inner_text().strip()
                        value = cells[1].inner_text().strip() if len(cells) > 1 else ""
                        if period:
                            data_points.append(IloDataPoint(period=period, value=value))

            return IloResult(
                queried_at=datetime.now(),
                country_code=country,
                indicator=indicator,
                data_points=data_points,
                details=f"ILO query: {indicator} for {country} — {len(data_points)} data points",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.ilo", f"Query failed: {e}") from e
