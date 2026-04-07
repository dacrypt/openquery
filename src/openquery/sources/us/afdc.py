"""AFDC Alternative Fuels Station Locator — US EV charging stations.

Queries the DOE Alternative Fuels Station (AFDC) API for EV charging
stations in the United States. Supports state, zip, and city filters.
Free API key from NREL (uses DEMO_KEY fallback).

API: https://developer.nrel.gov/api/alt-fuel-stations/v1.json
Docs: https://developer.nrel.gov/docs/transportation/alt-fuel-stations-v1/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.config import get_settings
from openquery.exceptions import SourceError
from openquery.models.us.afdc import AfdcResult, AfdcStation
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://developer.nrel.gov/api/alt-fuel-stations/v1.json"
DEMO_KEY = "DEMO_KEY"


@register
class AfdcSource(BaseSource):
    """Search US DOE AFDC for EV charging stations."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.afdc",
            display_name="DOE AFDC — Alternative Fuels Station Locator (US)",
            description=(
                "US Department of Energy Alternative Fuels Station Locator: "
                "EV charging stations by state, city, or ZIP code."
            ),
            country="US",
            url="https://afdc.energy.gov/stations/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        extra = input.extra or {}
        state = extra.get("state", "").strip().upper()
        zip_code = extra.get("zip", "").strip()
        city = extra.get("city", "").strip()

        if not state and not zip_code and not city:
            raise SourceError(
                "us.afdc",
                "Provide extra.state (US state code), extra.zip, or extra.city",
            )

        api_key = get_settings().nrel_api_key or DEMO_KEY
        return self._fetch(state, zip_code, city, api_key)

    def _fetch(self, state: str, zip_code: str, city: str, api_key: str) -> AfdcResult:
        try:
            params: dict[str, str] = {
                "fuel_type": "ELEC",
                "api_key": api_key,
                "limit": "100",
            }
            if state:
                params["state"] = state
            if zip_code:
                params["zip"] = zip_code
            if city:
                params["city"] = city

            search_parts = []
            if state:
                search_parts.append(f"state={state}")
            if zip_code:
                search_parts.append(f"zip={zip_code}")
            if city:
                search_parts.append(f"city={city}")
            search_str = " ".join(search_parts)

            logger.info("Querying AFDC: %s", search_str)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            raw_stations = data.get("fuel_stations", []) or []
            stations: list[AfdcStation] = []
            for s in raw_stations:
                connector_types = s.get("ev_connector_types") or []
                if isinstance(connector_types, str):
                    connector_types = [connector_types]

                stations.append(
                    AfdcStation(
                        name=s.get("station_name", "") or "",
                        street=s.get("street_address", "") or "",
                        city=s.get("city", "") or "",
                        state=s.get("state", "") or "",
                        zip=s.get("zip", "") or "",
                        latitude=float(s.get("latitude") or 0),
                        longitude=float(s.get("longitude") or 0),
                        ev_network=s.get("ev_network", "") or "",
                        ev_connector_types=connector_types,
                        ev_level2_count=int(s.get("ev_level2_evse_num") or 0),
                        ev_dc_fast_count=int(s.get("ev_dc_fast_num") or 0),
                        ev_pricing=s.get("ev_pricing", "") or "",
                        status=s.get("status_code", "") or "",
                    )
                )

            total = data.get("total_results", len(stations))
            logger.info("AFDC returned %d stations for: %s", len(stations), search_str)
            return AfdcResult(
                queried_at=datetime.now(),
                search_params=search_str,
                total_stations=total,
                stations=stations,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("us.afdc", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("us.afdc", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("us.afdc", f"Query failed: {e}") from e
