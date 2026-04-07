"""IEA Global EV data source — EV sales/stock/share by country.

Queries IEA Global EV Outlook data via CSV download.
Free, no auth required.

API: https://api.iea.org/evs?parameters=EV+sales&category=Historical&mode=Cars&csv=true
"""

from __future__ import annotations

import csv
import io
import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.iea_ev import IeaEvDataPoint, IntlIeaEvResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://api.iea.org/evs"

PARAMETER_MAP = {
    "ev sales": "EV sales",
    "ev stock": "EV stock",
    "ev share": "EV share",
    "ev_sales": "EV sales",
    "ev_stock": "EV stock",
    "ev_share": "EV share",
}


@register
class IeaEvSource(BaseSource):
    """Query IEA Global EV Outlook data by country and parameter."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.iea_ev",
            display_name="IEA — Global EV Outlook Data",
            description="IEA Global EV data: EV sales, stock, and share by country and year",
            country="INTL",
            url="https://www.iea.org/data-and-statistics/data-product/global-ev-outlook-2024",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        country = (input.extra.get("country") or input.document_number or "").strip()
        parameter_raw = input.extra.get("parameter", "EV sales").strip().lower()

        if not country:
            raise SourceError("intl.iea_ev", "Provide extra['country'] (country name or code)")

        parameter = PARAMETER_MAP.get(parameter_raw, parameter_raw)

        logger.info("Querying IEA EV data: country=%s parameter=%s", country, parameter)

        try:
            params = {
                "parameters": parameter,
                "category": "Historical",
                "mode": "Cars",
                "csv": "true",
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "text/csv,application/json",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                content = resp.text

            # Parse CSV content
            reader = csv.DictReader(io.StringIO(content))
            data_points = []
            country_lower = country.lower()
            matched_country = country

            for row in reader:
                row_country = row.get("region", row.get("country", row.get("Region", row.get("Country", ""))))  # noqa: E501
                if country_lower in row_country.lower():
                    matched_country = row_country
                    year_val = row.get("year", row.get("Year", ""))
                    value_val = row.get("value", row.get("Value", ""))
                    data_points.append(
                        IeaEvDataPoint(
                            year=str(year_val),
                            value=str(value_val),
                        )
                    )

            details = f"{len(data_points)} annual record(s) for {matched_country} ({parameter})"
            return IntlIeaEvResult(
                country=matched_country,
                parameter=parameter,
                data_points=data_points,
                details=details,
            )

        except SourceError:
            raise
        except httpx.HTTPStatusError as e:
            raise SourceError("intl.iea_ev", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("intl.iea_ev", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("intl.iea_ev", f"Query failed: {e}") from e
