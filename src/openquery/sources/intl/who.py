"""WHO Global Health Observatory OData API source.

Queries the WHO GHO OData API for health indicator data.
Free OData API, no auth, no CAPTCHA. Rate limit: 20 req/min.

API: https://ghoapi.azureedge.net/api/{indicator_code}
Docs: https://www.who.int/data/gho/info/gho-odata-api
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.who import WhoDataPoint, WhoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_BASE_URL = "https://ghoapi.azureedge.net/api/{indicator}"


@register
class WhoSource(BaseSource):
    """Query WHO Global Health Observatory indicator data."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.who",
            display_name="WHO Global Health Observatory",
            description="WHO GHO OData API for global health indicators (life expectancy, mortality, etc.)",
            country="INTL",
            url="https://www.who.int/data/gho/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        indicator = input.extra.get("indicator", input.document_number).strip()
        country = input.extra.get("country", "").strip().upper()

        if not indicator:
            raise SourceError("intl.who", "Provide an indicator code (extra.indicator or document_number), e.g. WHOSIS_000001")

        return self._fetch(indicator, country)

    def _fetch(self, indicator: str, country: str) -> WhoResult:
        url = API_BASE_URL.format(indicator=indicator)
        params: dict[str, str] = {"$format": "json"}
        if country:
            params["$filter"] = f"SpatialDim eq '{country}'"

        try:
            logger.info("Querying WHO GHO: indicator=%s country=%s", indicator, country)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

            # OData response: {"value": [...records...]}
            records = data.get("value", [])

            data_points: list[WhoDataPoint] = []
            for record in records:
                raw_value = record.get("NumericValue")
                value_str = str(raw_value) if raw_value is not None else ""
                data_points.append(WhoDataPoint(
                    country=record.get("SpatialDim", ""),
                    year=str(record.get("TimeDim", "")),
                    value=value_str,
                    sex=record.get("Dim1", ""),
                ))

            return WhoResult(
                queried_at=datetime.now(),
                indicator_code=indicator,
                country_code=country,
                total=len(data_points),
                data_points=data_points,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("intl.who", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("intl.who", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.who", f"Query failed: {e}") from e
