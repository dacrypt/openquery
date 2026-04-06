"""IMF DataMapper economic indicators source.

Queries the IMF DataMapper public REST API for country indicator data.
Free REST API, no auth, no CAPTCHA. Rate limit: 20 req/min.

API: https://www.imf.org/external/datamapper/api/v1/{indicator}/{country}
Docs: https://www.imf.org/external/datamapper/api/help
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.imf import ImfDataPoint, ImfResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_BASE_URL = "https://www.imf.org/external/datamapper/api/v1/{indicator}/{country}"
API_INDICATORS_URL = "https://www.imf.org/external/datamapper/api/v1/indicators/{indicator}"


@register
class ImfSource(BaseSource):
    """Query IMF DataMapper country indicator data."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.imf",
            display_name="IMF DataMapper — Economic Indicators",
            description="IMF DataMapper public API for country economic indicators (GDP growth, inflation, etc.)",  # noqa: E501
            country="INTL",
            url="https://www.imf.org/external/datamapper/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        country = input.extra.get("country", input.document_number).strip().upper()
        indicator = input.extra.get("indicator", "").strip()

        if not country:
            raise SourceError(
                "intl.imf", "Provide a country ISO3 code (extra.country or document_number)"
            )
        if not indicator:
            raise SourceError(
                "intl.imf", "Provide an indicator code (extra.indicator), e.g. NGDP_RPCH"
            )

        return self._fetch(country, indicator)

    def _fetch(self, country: str, indicator: str) -> ImfResult:
        url = API_BASE_URL.format(indicator=indicator, country=country)

        try:
            logger.info("Querying IMF DataMapper: country=%s indicator=%s", country, indicator)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()

            # Response structure: {"values": {indicator: {country: {year: value, ...}}}}
            values = data.get("values", {})
            indicator_values = values.get(indicator, {})
            country_values = indicator_values.get(country, {})

            # Fetch indicator metadata for the display name
            indicator_name = self._fetch_indicator_name(client, indicator)

            data_points: list[ImfDataPoint] = []
            for year, raw_value in sorted(country_values.items()):
                value_str = str(raw_value) if raw_value is not None else ""
                data_points.append(ImfDataPoint(year=year, value=value_str))

            return ImfResult(
                queried_at=datetime.now(),
                country_code=country,
                indicator_code=indicator,
                indicator_name=indicator_name,
                data_points=data_points,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("intl.imf", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("intl.imf", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.imf", f"Query failed: {e}") from e

    def _fetch_indicator_name(self, client: httpx.Client, indicator: str) -> str:
        """Fetch the human-readable indicator name from the IMF metadata endpoint."""
        try:
            meta_url = API_INDICATORS_URL.format(indicator=indicator)
            meta_resp = client.get(meta_url)
            if meta_resp.status_code == 200:
                meta_data = meta_resp.json()
                indicators = meta_data.get("indicators", {})
                ind_info = indicators.get(indicator, {})
                return ind_info.get("label", "")
        except Exception:
            pass
        return ""
