"""Bureau of Labor Statistics source — employment and price time series.

Queries the BLS public API v2 for employment statistics, CPI,
and other labor market time series. Free tier requires no API key.
Rate limit: 20 req/min.

API: https://api.bls.gov/publicAPI/v2/timeseries/data/
Docs: https://www.bls.gov/developers/api_signature_v2.htm
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.bls import BlsDataPoint, BlsResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# Well-known series names for display
SERIES_LABELS: dict[str, str] = {
    "CUUR0000SA0": "CPI-U All Items",
    "LNS14000000": "Unemployment Rate (Seasonally Adjusted)",
    "CES0000000001": "Total Nonfarm Employment",
    "WPUFD49104": "PPI Finished Goods",
}


@register
class BlsSource(BaseSource):
    """Query BLS employment and price time series data."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.bls",
            display_name="BLS — Bureau of Labor Statistics Time Series",
            description=(
                "US Bureau of Labor Statistics public API: CPI, unemployment, "
                "employment, and wage time series data"
            ),
            country="US",
            url="https://www.bls.gov/developers/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        series_id = input.extra.get("series_id", input.document_number).strip()

        if not series_id:
            raise SourceError(
                "us.bls",
                "Provide a BLS series ID (extra.series_id or document_number), "
                "e.g. CUUR0000SA0",
            )

        return self._fetch(series_id)

    def _fetch(self, series_id: str) -> BlsResult:
        payload = {
            "seriesid": [series_id],
            "startyear": "2020",
            "endyear": str(datetime.now().year),
        }

        try:
            logger.info("Querying BLS: series_id=%s", series_id)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Content-Type": "application/json",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.post(BLS_API_URL, json=payload)
                resp.raise_for_status()
                data = resp.json()

            if data.get("status") != "REQUEST_SUCCEEDED":
                message = data.get("message", ["Unknown error"])
                msg_str = message[0] if isinstance(message, list) and message else str(message)
                raise SourceError("us.bls", f"BLS API error: {msg_str}")

            results = data.get("Results", {})
            series_list = results.get("series", [])

            data_points: list[BlsDataPoint] = []
            series_name = SERIES_LABELS.get(series_id, "")

            if series_list:
                series_data = series_list[0]
                series_name = series_name or series_data.get("seriesID", series_id)
                for obs in series_data.get("data", []):
                    data_points.append(
                        BlsDataPoint(
                            year=str(obs.get("year", "")),
                            period=str(obs.get("periodName", obs.get("period", ""))),
                            value=str(obs.get("value", "")),
                        )
                    )

            return BlsResult(
                queried_at=datetime.now(),
                series_id=series_id,
                series_name=series_name,
                data_points=data_points,
                details=f"BLS series {series_id}",
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "us.bls", f"BLS API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("us.bls", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("us.bls", f"Query failed: {e}") from e
