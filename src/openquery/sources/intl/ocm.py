"""Open Charge Map source — global EV charging station locator.

Queries the Open Charge Map (OCM) public API for EV charging stations
worldwide. Supports country-code search, radius search (lat/lon/distance),
and city filter. Free API key required (register at openchargemap.io).

API: https://api.openchargemap.io/v3/poi/
Docs: https://openchargemap.org/site/develop/api
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.config import get_settings
from openquery.exceptions import SourceError
from openquery.models.intl.ocm import OcmConnector, OcmResult, OcmStation
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://api.openchargemap.io/v3/poi/"


@register
class OcmSource(BaseSource):
    """Search Open Charge Map for EV charging stations globally."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.ocm",
            display_name="Open Charge Map — EV Charging Stations (Global)",
            description=(
                "Open Charge Map: global EV charging station locator. "
                "Search by country, city, or lat/lon radius."
            ),
            country="INTL",
            url="https://openchargemap.org/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        extra = input.extra or {}
        country = extra.get("country", "").strip().upper()
        city = extra.get("city", "").strip()
        latitude = extra.get("latitude", "")
        longitude = extra.get("longitude", "")
        distance = extra.get("distance", "")

        if not country and not (latitude and longitude):
            raise SourceError(
                "intl.ocm",
                "Provide extra.country (ISO2) or extra.latitude + extra.longitude",
            )

        api_key = get_settings().ocm_api_key
        return self._fetch(country, city, latitude, longitude, distance, api_key)

    def _fetch(
        self,
        country: str,
        city: str,
        latitude: str | float,
        longitude: str | float,
        distance: str | float,
        api_key: str,
    ) -> OcmResult:
        try:
            params: dict[str, str | int] = {
                "output": "json",
                "maxresults": 100,
                "compact": "true",
                "verbose": "false",
            }

            if country:
                params["countrycode"] = country
            if latitude and longitude:
                params["latitude"] = str(latitude)
                params["longitude"] = str(longitude)
                params["distance"] = str(distance) if distance else "25"
                params["distanceunit"] = "km"
            if city:
                params["city"] = city
            if api_key:
                params["key"] = api_key

            search_parts = []
            if country:
                search_parts.append(f"country={country}")
            if city:
                search_parts.append(f"city={city}")
            if latitude and longitude:
                search_parts.append(f"lat={latitude},lon={longitude},dist={distance or 25}km")
            search_str = " ".join(search_parts)

            logger.info("Querying OCM: %s", search_str)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            stations: list[OcmStation] = []
            for item in data:
                addr_info = item.get("AddressInfo", {}) or {}
                op_info = item.get("OperatorInfo", {}) or {}
                status_type = item.get("StatusType", {}) or {}
                usage_type = item.get("UsageType", {}) or {}

                connectors: list[OcmConnector] = []
                for conn in item.get("Connections", []) or []:
                    ct = conn.get("ConnectionType", {}) or {}
                    level = conn.get("Level", {}) or {}
                    connectors.append(
                        OcmConnector(
                            connector_type=ct.get("Title", "") or "",
                            power_kw=float(conn.get("PowerKW") or 0),
                            voltage=int(conn.get("Voltage") or 0),
                            amps=int(conn.get("Amps") or 0),
                            current_type=level.get("Title", "") or "",
                        )
                    )

                stations.append(
                    OcmStation(
                        name=addr_info.get("Title", "") or "",
                        operator=op_info.get("Title", "") or "",
                        address=addr_info.get("AddressLine1", "") or "",
                        city=addr_info.get("Town", "") or "",
                        country=addr_info.get("Country", {}).get("ISOCode", "") if isinstance(addr_info.get("Country"), dict) else "",  # noqa: E501
                        latitude=float(addr_info.get("Latitude") or 0),
                        longitude=float(addr_info.get("Longitude") or 0),
                        num_points=int(item.get("NumberOfPoints") or 0),
                        status=status_type.get("Title", "") or "",
                        usage_type=usage_type.get("Title", "") or "",
                        connectors=connectors,
                    )
                )

            logger.info("OCM returned %d stations for: %s", len(stations), search_str)
            return OcmResult(
                queried_at=datetime.now(),
                search_params=search_str,
                total_stations=len(stations),
                stations=stations,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("intl.ocm", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("intl.ocm", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.ocm", f"Query failed: {e}") from e
