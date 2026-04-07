"""EIA energy data source — US electricity/fuel prices.

Queries EIA (Energy Information Administration) API for electricity retail sales.
Requires free API key from eia.gov/opendata.

API: https://api.eia.gov/v2/electricity/retail-sales/data/
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.eia import EiaDataPoint, UsEiaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://api.eia.gov/v2/electricity/retail-sales/data/"

SECTOR_MAP = {
    "residential": "RES",
    "commercial": "COM",
    "industrial": "IND",
    "transportation": "TRA",
    "all": "ALL",
}


@register
class EiaSource(BaseSource):
    """Query EIA electricity retail prices by state and sector."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.eia",
            display_name="EIA — US Electricity Retail Prices",
            description="US electricity retail sales and prices by state/sector from EIA API",
            country="US",
            url="https://api.eia.gov/v2/electricity/retail-sales/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        from openquery.config import get_settings

        settings = get_settings()
        api_key = settings.eia_api_key
        if not api_key:
            raise SourceError("us.eia", "OPENQUERY_EIA_API_KEY is not configured")

        state = (input.extra.get("state") or input.document_number or "").strip().upper()
        sector_raw = input.extra.get("sector", "residential").strip().lower()

        if not state:
            raise SourceError("us.eia", "Provide extra['state'] (2-letter state code)")

        sector_id = SECTOR_MAP.get(sector_raw, "RES")

        params: dict[str, str] = {
            "api_key": api_key,
            "frequency": "monthly",
            "data[0]": "price",
            "facets[sectorid][]": sector_id,
            "facets[stateid][]": state,
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": "24",
            "offset": "0",
        }

        logger.info("Querying EIA electricity prices: state=%s sector=%s", state, sector_raw)

        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            response_data = data.get("response", {})
            records = response_data.get("data", [])

            data_points = []
            for rec in records:
                data_points.append(
                    EiaDataPoint(
                        period=str(rec.get("period", "")),
                        price=str(rec.get("price", "")),
                    )
                )

            details = f"{len(data_points)} monthly records for {state} ({sector_raw})"
            return UsEiaResult(
                state=state,
                sector=sector_raw,
                data_points=data_points,
                details=details,
            )

        except SourceError:
            raise
        except httpx.HTTPStatusError as e:
            raise SourceError("us.eia", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("us.eia", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("us.eia", f"Query failed: {e}") from e
