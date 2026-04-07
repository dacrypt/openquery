"""US auto sales source — FRED API vehicle sales time series.

Queries the Federal Reserve FRED API for US total vehicle sales data.
Supports multiple series:
  - TOTALSA  : Total Vehicle Sales (millions of units, SAAR)
  - LAUTOSA  : Light Weight Vehicle Sales (millions of units, SAAR)
  - HTRUCKSSA: Heavy Trucks Sales (thousands of units, SAAR)

Free API key available at https://fredaccount.stlouisfed.org/
Set OPENQUERY_FRED_API_KEY to use your own key.

API: https://api.stlouisfed.org/fred/series/observations
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.auto_sales import AutoSalesDataPoint, AutoSalesResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

FRED_SERIES_URL = "https://api.stlouisfed.org/fred/series"
FRED_OBS_URL = "https://api.stlouisfed.org/fred/series/observations"

FRED_DEMO_KEY = "DEMO"

DEFAULT_SERIES_ID = "TOTALSA"

KNOWN_SERIES: dict[str, str] = {
    "TOTALSA": "Total Vehicle Sales",
    "LAUTOSA": "Light Weight Vehicle Sales",
    "HTRUCKSSA": "Heavy Trucks Sales",
}


@register
class AutoSalesSource(BaseSource):
    """Query US vehicle sales time series from FRED."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.auto_sales",
            display_name="US Auto Sales — FRED (Federal Reserve)",
            description=(
                "US total vehicle sales time series from the Federal Reserve FRED API. "
                "Supports TOTALSA (total), LAUTOSA (light autos), HTRUCKSSA (heavy trucks)"
            ),
            country="US",
            url="https://fred.stlouisfed.org/series/TOTALSA",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        series_id = input.extra.get("series_id", DEFAULT_SERIES_ID).strip().upper()
        if not series_id:
            series_id = DEFAULT_SERIES_ID

        from openquery.config import get_settings

        settings = get_settings()
        api_key = input.extra.get("api_key", settings.fred_api_key or FRED_DEMO_KEY).strip()

        return self._fetch(series_id, api_key)

    def _fetch(self, series_id: str, api_key: str) -> AutoSalesResult:
        try:
            logger.info("Querying FRED auto sales: series_id=%s", series_id)

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

                series_name = KNOWN_SERIES.get(series_id, "")
                series_list = meta_data.get("seriess", [])
                if series_list:
                    series_name = series_list[0].get("title", series_name)
                    frequency = series_list[0].get("frequency_short", "M")
                else:
                    frequency = "M"

                # Fetch observations (last 50 data points)
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

            data_points: list[AutoSalesDataPoint] = []
            for obs in reversed(obs_data.get("observations", [])):
                raw_val = obs.get("value", "")
                value_str = "" if raw_val == "." else str(raw_val)
                data_points.append(
                    AutoSalesDataPoint(
                        date=str(obs.get("date", "")),
                        value=value_str,
                    )
                )

            return AutoSalesResult(
                queried_at=datetime.now(),
                series_id=series_id,
                series_name=series_name,
                frequency=frequency,
                total_observations=len(data_points),
                data_points=data_points,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "us.auto_sales", f"FRED API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("us.auto_sales", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("us.auto_sales", f"Query failed: {e}") from e
