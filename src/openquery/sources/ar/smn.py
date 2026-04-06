"""SMN weather/climate data source — Argentina.

Queries SMN (Servicio Meteorológico Nacional) for weather data by city.

URL: https://www.smn.gob.ar/
Input: city name (custom)
Returns: temperature, conditions
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.smn import SmnResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SMN_API_URL = "https://ws.smn.gob.ar/map_items/weather"


@register
class SmnSource(BaseSource):
    """Query SMN for weather data by city."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.smn",
            display_name="SMN — Servicio Meteorológico Nacional",
            description="Argentina SMN: current weather data lookup by city name",
            country="AR",
            url="https://www.smn.gob.ar/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        city = (input.extra.get("city", "") or input.document_number).strip()
        if not city:
            raise SourceError("ar.smn", "City name required (extra.city or document_number)")
        return self._fetch(city)

    def _fetch(self, city: str) -> SmnResult:
        try:
            logger.info("Querying SMN: city=%s", city)
            headers = {"User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)"}
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(SMN_API_URL)
                resp.raise_for_status()
                data = resp.json()

            temperature = ""
            conditions = ""

            if isinstance(data, list):
                for item in data:
                    name = item.get("name", "") or item.get("ciudad", "") or item.get("station", {}).get("name", "")  # noqa: E501
                    if city.lower() in name.lower():
                        weather = item.get("weather", item)
                        temperature = str(weather.get("temp", weather.get("temperatura", "")))
                        conditions = weather.get("description", weather.get("tiempo", weather.get("condition", "")))  # noqa: E501
                        break

            return SmnResult(
                queried_at=datetime.now(),
                city=city,
                temperature=temperature,
                conditions=conditions,
                details=f"SMN weather query for: {city}",
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("ar.smn", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("ar.smn", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("ar.smn", f"Query failed: {e}") from e
