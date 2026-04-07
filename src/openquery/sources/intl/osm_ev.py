"""OpenStreetMap EV charging stations source — global Overpass API.

Queries the Overpass API for EV charging station nodes tagged with
amenity=charging_station in OpenStreetMap. Supports country-code search
and radius search (lat/lon/radius). No authentication required.

API: https://overpass-api.de/api/interpreter
Docs: https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.osm_ev import OsmEvResult, OsmEvStation
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Socket-type tags to extract from OSM node tags
_SOCKET_TAGS = [
    "socket:type2",
    "socket:ccs",
    "socket:chademo",
    "socket:type1",
    "socket:schuko",
    "socket:tesla_supercharger",
    "socket:type2_combo",
]


@register
class OsmEvSource(BaseSource):
    """Query OpenStreetMap Overpass API for EV charging stations."""

    def __init__(self, timeout: float = 60.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.osm_ev",
            display_name="OpenStreetMap — EV Charging Stations (Global, Overpass)",
            description=(
                "OpenStreetMap EV charging station nodes via Overpass API. "
                "Search by country (ISO2) or lat/lon radius."
            ),
            country="INTL",
            url="https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dcharging_station",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=5,
        )

    def query(self, input: QueryInput) -> BaseModel:
        extra = input.extra or {}
        country = extra.get("country", "").strip().upper()
        latitude = extra.get("latitude", "")
        longitude = extra.get("longitude", "")
        radius = extra.get("radius", "5000")  # metres, default 5km

        if not country and not (latitude and longitude):
            raise SourceError(
                "intl.osm_ev",
                "Provide extra.country (ISO2) or extra.latitude + extra.longitude",
            )

        return self._fetch(country, latitude, longitude, radius)

    def _build_query(
        self,
        country: str,
        latitude: str | float,
        longitude: str | float,
        radius: str | float,
    ) -> str:
        if country:
            return (
                f'[out:json][timeout:30];\n'
                f'area["ISO3166-1"="{country}"]->.searchArea;\n'
                f'node["amenity"="charging_station"](area.searchArea);\n'
                f'out body;'
            )
        # Radius search (metres)
        return (
            f'[out:json][timeout:30];\n'
            f'node["amenity"="charging_station"]'
            f'(around:{radius},{latitude},{longitude});\n'
            f'out body;'
        )

    def _fetch(
        self,
        country: str,
        latitude: str | float,
        longitude: str | float,
        radius: str | float,
    ) -> OsmEvResult:
        try:
            search_parts = []
            if country:
                search_parts.append(f"country={country}")
            if latitude and longitude:
                search_parts.append(f"lat={latitude},lon={longitude},radius={radius}m")
            search_str = " ".join(search_parts)

            query = self._build_query(country, latitude, longitude, radius)
            logger.info("Querying Overpass for EV stations: %s", search_str)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.post(OVERPASS_URL, data={"data": query})
                resp.raise_for_status()
                data = resp.json()

            elements = data.get("elements", []) or []
            stations: list[OsmEvStation] = []
            for el in elements:
                if el.get("type") != "node":
                    continue

                tags = el.get("tags", {}) or {}

                # Collect socket types that are present
                socket_types = [
                    tag for tag in _SOCKET_TAGS if tags.get(tag) and tags[tag] != "no"
                ]

                stations.append(
                    OsmEvStation(
                        osm_id=int(el.get("id", 0)),
                        latitude=float(el.get("lat", 0)),
                        longitude=float(el.get("lon", 0)),
                        operator=tags.get("operator", "") or "",
                        capacity=tags.get("capacity", "") or "",
                        socket_types=socket_types,
                        fee=tags.get("fee", "") or "",
                        opening_hours=tags.get("opening_hours", "") or "",
                    )
                )

            logger.info("Overpass returned %d EV stations for: %s", len(stations), search_str)
            return OsmEvResult(
                queried_at=datetime.now(),
                search_params=search_str,
                total_stations=len(stations),
                stations=stations,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "intl.osm_ev", f"Overpass API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("intl.osm_ev", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.osm_ev", f"Query failed: {e}") from e
