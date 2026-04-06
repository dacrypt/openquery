"""World Development Indicators source.

Queries the World Bank DataBank API for WDI data.
Free REST API, no auth, no CAPTCHA.

API: https://api.worldbank.org/v2/country/{code}/indicator/{indicator}?format=json
Docs: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.wdi import WdiDataPoint, WdiResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

WDI_API_URL = "https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"


@register
class WdiSource(BaseSource):
    """Query World Development Indicators via World Bank API."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.wdi",
            display_name="World Bank — World Development Indicators",
            description=(
                "World Development Indicators: detailed country-level statistics "
                "via World Bank DataBank API"
            ),
            country="INTL",
            url="https://databank.worldbank.org/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        country = input.extra.get("country", input.document_number).strip().upper()
        indicator = input.extra.get("indicator", "").strip()

        if not country:
            raise SourceError(
                "intl.wdi",
                "Provide a country ISO2 code (extra.country or document_number)",
            )
        if not indicator:
            raise SourceError(
                "intl.wdi",
                "Provide an indicator code (extra.indicator), e.g. NY.GDP.MKTP.CD",
            )

        return self._fetch(country, indicator)

    def _fetch(self, country: str, indicator: str) -> WdiResult:
        url = WDI_API_URL.format(country=country, indicator=indicator)
        params = {"format": "json", "per_page": "50", "mrv": "10"}

        try:
            logger.info("Querying WDI: country=%s indicator=%s", country, indicator)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

            if not isinstance(data, list) or len(data) < 2:
                raise SourceError("intl.wdi", "Unexpected API response format")

            records = data[1] or []
            data_points: list[WdiDataPoint] = []

            for record in records:
                raw_value = record.get("value")
                value_str = str(raw_value) if raw_value is not None else ""
                data_points.append(
                    WdiDataPoint(
                        year=record.get("date", ""),
                        value=value_str,
                    )
                )

            return WdiResult(
                queried_at=datetime.now(),
                country_code=country,
                indicator=indicator,
                data_points=data_points,
                details=f"WDI: {indicator} for {country} — {len(data_points)} data points",
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "intl.wdi", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("intl.wdi", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.wdi", f"Query failed: {e}") from e
