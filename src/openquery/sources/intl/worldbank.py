"""World Bank country indicators source.

Queries the World Bank public REST API for country indicator data.
Free REST API, no auth, no CAPTCHA. Rate limit: 30 req/min.

API: https://api.worldbank.org/v2/country/{code}/indicator/{indicator}?format=json
Docs: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.worldbank import WorldBankDataPoint, WorldBankResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_BASE_URL = "https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"


@register
class WorldBankSource(BaseSource):
    """Query World Bank country indicator data."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.worldbank",
            display_name="World Bank — Country Indicators",
            description="World Bank public API for country development indicators (GDP, population, etc.)",
            country="INTL",
            url="https://data.worldbank.org/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        country = input.extra.get("country", input.document_number).strip().upper()
        indicator = input.extra.get("indicator", "").strip()

        if not country:
            raise SourceError("intl.worldbank", "Provide a country ISO2 code (extra.country or document_number)")
        if not indicator:
            raise SourceError("intl.worldbank", "Provide an indicator code (extra.indicator), e.g. NY.GDP.MKTP.CD")

        return self._fetch(country, indicator)

    def _fetch(self, country: str, indicator: str) -> WorldBankResult:
        url = API_BASE_URL.format(country=country, indicator=indicator)
        params = {"format": "json", "per_page": "50"}

        try:
            logger.info("Querying World Bank: country=%s indicator=%s", country, indicator)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

            # Response is a 2-element array: [page_info, data_array]
            if not isinstance(data, list) or len(data) < 2:
                raise SourceError("intl.worldbank", "Unexpected API response format")

            records = data[1] or []

            country_name = ""
            indicator_name = ""
            data_points: list[WorldBankDataPoint] = []

            for record in records:
                if not country_name:
                    country_info = record.get("country", {})
                    country_name = country_info.get("value", "") if isinstance(country_info, dict) else ""
                if not indicator_name:
                    ind_info = record.get("indicator", {})
                    indicator_name = ind_info.get("value", "") if isinstance(ind_info, dict) else ""

                raw_value = record.get("value")
                value_str = str(raw_value) if raw_value is not None else ""
                data_points.append(WorldBankDataPoint(
                    year=record.get("date", ""),
                    value=value_str,
                ))

            return WorldBankResult(
                queried_at=datetime.now(),
                country_code=country,
                country_name=country_name,
                indicator_code=indicator,
                indicator_name=indicator_name,
                data_points=data_points,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("intl.worldbank", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("intl.worldbank", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.worldbank", f"Query failed: {e}") from e
