"""Federal Reserve FRED source — economic time series data.

Queries the FRED (Federal Reserve Economic Data) API for economic
time series such as GDP, unemployment rate, federal funds rate, etc.
Free API key available; uses DEMO key fallback for basic access.
Rate limit: 20 req/min.

API: https://api.stlouisfed.org/fred/
Docs: https://fred.stlouisfed.org/docs/api/fred/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.fred import FredDataPoint, FredResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

FRED_SERIES_URL = "https://api.stlouisfed.org/fred/series"
FRED_OBS_URL = "https://api.stlouisfed.org/fred/series/observations"

# Public demo key with limited access — users should set OPENQUERY_FRED_API_KEY
FRED_DEMO_KEY = "DEMO"


@register
class FredSource(BaseSource):
    """Query Federal Reserve FRED economic time series data."""

    def __init__(self, timeout: float = 30.0, api_key: str = FRED_DEMO_KEY) -> None:
        self._timeout = timeout
        self._api_key = api_key

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.fred",
            display_name="Federal Reserve FRED — Economic Time Series",
            description=(
                "Federal Reserve Bank of St. Louis FRED API: GDP, unemployment, "
                "inflation, interest rates, and 800,000+ economic time series"
            ),
            country="US",
            url="https://fred.stlouisfed.org/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        series_id = input.extra.get("series_id", input.document_number).strip().upper()

        if not series_id:
            raise SourceError(
                "us.fred",
                "Provide a FRED series ID (extra.series_id or document_number), e.g. GDP",
            )

        api_key = input.extra.get("api_key", self._api_key).strip()
        return self._fetch(series_id, api_key)

    def _fetch(self, series_id: str, api_key: str) -> FredResult:
        try:
            logger.info("Querying FRED: series_id=%s", series_id)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                # Fetch series metadata
                meta_params = {
                    "series_id": series_id,
                    "api_key": api_key,
                    "file_type": "json",
                }
                meta_resp = client.get(FRED_SERIES_URL, params=meta_params)
                meta_resp.raise_for_status()
                meta_data = meta_resp.json()

                series_name = ""
                series_list = meta_data.get("seriess", [])
                if series_list:
                    series_name = series_list[0].get("title", "")

                # Fetch observations (last 20 years)
                obs_params = {
                    "series_id": series_id,
                    "api_key": api_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": "50",
                }
                obs_resp = client.get(FRED_OBS_URL, params=obs_params)
                obs_resp.raise_for_status()
                obs_data = obs_resp.json()

            data_points: list[FredDataPoint] = []
            for obs in reversed(obs_data.get("observations", [])):
                raw_val = obs.get("value", "")
                # FRED uses "." for missing values
                value_str = "" if raw_val == "." else str(raw_val)
                data_points.append(
                    FredDataPoint(
                        date=str(obs.get("date", "")),
                        value=value_str,
                    )
                )

            return FredResult(
                queried_at=datetime.now(),
                series_id=series_id,
                series_name=series_name,
                data_points=data_points,
                details=f"FRED series {series_id}: {series_name}",
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "us.fred", f"FRED API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("us.fred", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("us.fred", f"Query failed: {e}") from e
