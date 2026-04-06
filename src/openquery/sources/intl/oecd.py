"""OECD statistics source — economic indicator data.

Queries the OECD SDMX REST API for country economic indicators.
Free REST API, no auth, no CAPTCHA. Rate limit: 20 req/min.

API: https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_KEI@DF_KEI,4.0/
Docs: https://data.oecd.org/api/sdmx-json-documentation/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.oecd import OecdDataPoint, OecdResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_BASE_URL = (
    "https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_KEI@DF_KEI,4.0/"
    "{country}.{indicator}....."
)


@register
class OecdSource(BaseSource):
    """Query OECD economic indicator data via the SDMX REST API."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.oecd",
            display_name="OECD — Economic Indicators (KEI)",
            description=(
                "OECD Key Economic Indicators via SDMX REST API "
                "(GDP, inflation, unemployment, etc.)"
            ),
            country="INTL",
            url="https://data.oecd.org/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        country = input.extra.get("country", input.document_number).strip().upper()
        indicator = input.extra.get("indicator", "").strip().upper()

        if not country:
            raise SourceError(
                "intl.oecd",
                "Provide a country ISO2 code (extra.country or document_number)",
            )
        if not indicator:
            raise SourceError(
                "intl.oecd",
                "Provide an indicator code (extra.indicator), e.g. CPI01",
            )

        return self._fetch(country, indicator)

    def _fetch(self, country: str, indicator: str) -> OecdResult:
        url = API_BASE_URL.format(country=country, indicator=indicator)
        params = {"format": "jsondata", "startPeriod": "2015"}

        try:
            logger.info("Querying OECD KEI: country=%s indicator=%s", country, indicator)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

            data_points: list[OecdDataPoint] = []
            details = ""

            # SDMX-JSON structure: data.dataSets[0].series -> observations
            datasets = data.get("data", {}).get("dataSets", [])
            structures_list = data.get("data", {}).get("structures", [])
            structure = structures_list[0] if structures_list else {}

            # Extract time dimension labels
            dimensions = structure.get("dimensions", {})
            time_dims = dimensions.get("observation", [])
            time_labels: list[str] = []
            for dim in time_dims:
                if dim.get("id") == "TIME_PERIOD":
                    time_labels = [v.get("id", "") for v in dim.get("values", [])]
                    break

            # Extract series name from attributes
            series_info = structure.get("attributes", {}).get("series", [])
            if series_info:
                details = series_info[0].get("name", "")

            if datasets:
                series_map = datasets[0].get("series", {})
                for _series_key, series_val in series_map.items():
                    observations = series_val.get("observations", {})
                    for idx_str, obs_vals in sorted(
                        observations.items(), key=lambda x: int(x[0])
                    ):
                        idx = int(idx_str)
                        period = time_labels[idx] if idx < len(time_labels) else idx_str
                        raw_val = obs_vals[0] if obs_vals else None
                        value_str = str(raw_val) if raw_val is not None else ""
                        data_points.append(OecdDataPoint(period=period, value=value_str))

            return OecdResult(
                queried_at=datetime.now(),
                country_code=country,
                indicator_code=indicator,
                data_points=data_points,
                details=details,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "intl.oecd", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("intl.oecd", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.oecd", f"Query failed: {e}") from e
