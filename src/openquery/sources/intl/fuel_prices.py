"""Fuel prices source — World Bank global fuel prices.

Queries World Bank API for gasoline/diesel prices by country.
Free REST API, no auth required. Rate limit: ~20 req/min.

API: https://api.worldbank.org/v2/country/{iso2}/indicator/EP.PMP.SGAS.CD
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.fuel_prices import FuelPriceDataPoint, IntlFuelPricesResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

# World Bank indicator codes
INDICATOR_MAP = {
    "gasoline": "EP.PMP.SGAS.CD",
    "diesel": "EP.PMP.DESL.CD",
}

API_BASE = "https://api.worldbank.org/v2/country/{iso2}/indicator/{indicator}"


@register
class FuelPricesSource(BaseSource):
    """Query World Bank global fuel prices by country."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.fuel_prices",
            display_name="World Bank — Global Fuel Prices",
            description="Global fuel prices (gasoline/diesel) by country from World Bank API",
            country="INTL",
            url="https://api.worldbank.org/v2/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        country = (input.extra.get("country") or input.document_number or "").strip().upper()
        fuel_type = input.extra.get("fuel_type", "gasoline").strip().lower()

        if not country:
            raise SourceError("intl.fuel_prices", "Provide extra['country'] (ISO2 code)")

        indicator = INDICATOR_MAP.get(fuel_type, INDICATOR_MAP["gasoline"])

        url = API_BASE.format(iso2=country, indicator=indicator)
        params = {"format": "json", "per_page": "50", "mrv": "12"}

        logger.info("Querying World Bank fuel prices: country=%s fuel=%s", country, fuel_type)

        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

            if not isinstance(data, list) or len(data) < 2:
                raise SourceError("intl.fuel_prices", "Unexpected API response format")

            records = data[1] or []
            data_points = []
            for rec in records:
                if rec is None:
                    continue
                value = rec.get("value")
                data_points.append(
                    FuelPriceDataPoint(
                        date=str(rec.get("date", "")),
                        price=str(value) if value is not None else "",
                        currency="USD",
                    )
                )

            details = f"{len(data_points)} data points for {country} ({fuel_type})"
            return IntlFuelPricesResult(
                country_code=country,
                fuel_type=fuel_type,
                data_points=data_points,
                details=details,
            )

        except SourceError:
            raise
        except httpx.HTTPStatusError as e:
            raise SourceError("intl.fuel_prices", f"API returned HTTP {e.response.status_code}") from e  # noqa: E501
        except httpx.RequestError as e:
            raise SourceError("intl.fuel_prices", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("intl.fuel_prices", f"Query failed: {e}") from e
