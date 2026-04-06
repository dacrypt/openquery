"""FCC broadband availability source.

Queries the FCC National Broadband Map API for broadband provider
availability by location (address or lat/lon).
Free REST API, no auth required. Rate limit: 10 req/min.

API: https://broadbandmap.fcc.gov/api/
Docs: https://broadbandmap.fcc.gov/about
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.fcc_broadband import FccBroadbandResult, FccProvider
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

FCC_LOCATION_URL = "https://broadbandmap.fcc.gov/api/public/map/listAvailability"

# FCC technology codes
TECH_CODES: dict[int, str] = {
    10: "DSL",
    40: "Cable",
    50: "Fiber",
    60: "Satellite",
    70: "Fixed Wireless",
    300: "LTE",
    400: "5G-NR",
}


@register
class FccBroadbandSource(BaseSource):
    """Query FCC National Broadband Map for provider availability by location."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.fcc_broadband",
            display_name="FCC — National Broadband Map",
            description=(
                "FCC National Broadband Map: broadband provider availability, "
                "technology types, and advertised speeds by location"
            ),
            country="US",
            url="https://broadbandmap.fcc.gov/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        location = input.extra.get("location", input.document_number).strip()
        latitude = input.extra.get("latitude", "").strip()
        longitude = input.extra.get("longitude", "").strip()

        if not location and not (latitude and longitude):
            raise SourceError(
                "us.fcc_broadband",
                "Provide a location (extra.location or document_number) "
                "or coordinates (extra.latitude + extra.longitude)",
            )

        query_location = location or f"{latitude},{longitude}"
        return self._fetch(query_location, latitude, longitude)

    def _fetch(self, location: str, latitude: str, longitude: str) -> FccBroadbandResult:
        try:
            logger.info("Querying FCC broadband map: location=%s", location)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
                "Origin": "https://broadbandmap.fcc.gov",
                "Referer": "https://broadbandmap.fcc.gov/",
            }

            providers: list[FccProvider] = []
            details = ""

            with httpx.Client(
                timeout=self._timeout, headers=headers, follow_redirects=True
            ) as client:
                if latitude and longitude:
                    params: dict[str, str] = {
                        "latitude": latitude,
                        "longitude": longitude,
                        "unit": "location",
                    }
                else:
                    # Use address-based lookup
                    params = {
                        "address": location,
                        "unit": "location",
                    }

                resp = client.get(FCC_LOCATION_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            # Parse provider list
            availability = data.get("availability", data.get("results", []))
            if isinstance(availability, dict):
                availability = availability.get("data", [])

            for entry in availability:
                tech_code = entry.get("technology", entry.get("tech_code", 0))
                tech_name = TECH_CODES.get(int(tech_code), str(tech_code))
                down = entry.get("max_advertised_download_speed", entry.get("download_speed", ""))
                up = entry.get("max_advertised_upload_speed", entry.get("upload_speed", ""))
                speed_str = f"{down}/{up} Mbps" if down or up else ""

                providers.append(
                    FccProvider(
                        name=str(entry.get("brand_name", entry.get("provider_name", ""))),
                        technology=tech_name,
                        speed=speed_str,
                    )
                )

            if not providers:
                details = "No broadband availability data found for this location"

            return FccBroadbandResult(
                queried_at=datetime.now(),
                location=location,
                providers=providers,
                details=details,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "us.fcc_broadband", f"FCC API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("us.fcc_broadband", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("us.fcc_broadband", f"Query failed: {e}") from e
