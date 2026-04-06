"""EPA Fuel Economy source — US vehicle efficiency ratings (MPG/MPGe).

Queries the fueleconomy.gov REST API to look up EPA fuel economy data
for a given make, model, and year.  Uses a multi-step flow:

  1. Resolve model options: /ws/rest/vehicle/menu/options?year=&make=&model=
  2. For each option, fetch full record: /ws/rest/vehicle/{id}

No browser or CAPTCHA required — direct HTTP API.

API: https://www.fueleconomy.gov/ws/rest/vehicle/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.epa_fuel_economy import EpaFuelEconomyResult, EpaVehicle
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

BASE_URL = "https://www.fueleconomy.gov/ws/rest/vehicle"
_HEADERS = {"Accept": "application/json"}


@register
class EpaFuelEconomySource(BaseSource):
    """Look up EPA fuel economy ratings by make/model/year."""

    def __init__(self, timeout: float = 20.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.epa_fuel_economy",
            display_name="EPA — Fuel Economy",
            description="US EPA vehicle fuel economy ratings (MPG/MPGe)",
            country="US",
            url="https://www.fueleconomy.gov/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query EPA fuel economy data for a given make/model/year."""
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError(
                "us.epa_fuel_economy", f"Unsupported input type: {input.document_type}"
            )

        make = input.extra.get("make", "").strip()
        model = input.extra.get("model", "").strip()
        year = str(input.extra.get("year", "")).strip()

        if not make or not model or not year:
            raise SourceError("us.epa_fuel_economy", "make, model, and year are required in extra")

        try:
            logger.info("Querying EPA fuel economy for %s %s %s", year, make, model)

            with httpx.Client(timeout=self._timeout, headers=_HEADERS) as client:
                # Step 1: Get vehicle options (trim levels) for this make/model/year
                options_url = f"{BASE_URL}/menu/options"
                resp = client.get(
                    options_url,
                    params={"year": year, "make": make, "model": model},
                )
                resp.raise_for_status()
                options_data = resp.json()

                # The API returns {"menuItem": [...]} or {"menuItem": {...}} for single
                menu_items = options_data.get("menuItem", [])
                if isinstance(menu_items, dict):
                    menu_items = [menu_items]

                # Step 2: Fetch full vehicle record for each option
                vehicles: list[EpaVehicle] = []
                for item in menu_items:
                    vehicle_id = str(item.get("value", ""))
                    if not vehicle_id:
                        continue

                    vehicle_url = f"{BASE_URL}/{vehicle_id}"
                    vresp = client.get(vehicle_url)
                    vresp.raise_for_status()
                    vdata = vresp.json()

                    vehicles.append(
                        EpaVehicle(
                            vehicle_id=vehicle_id,
                            make=str(vdata.get("make", "")),
                            model=str(vdata.get("model", "")),
                            year=str(vdata.get("year", "")),
                            fuel_type=str(vdata.get("fuelType", "")),
                            city_mpg=str(vdata.get("city08", "")),
                            highway_mpg=str(vdata.get("highway08", "")),
                            combined_mpg=str(vdata.get("comb08", "")),
                            co2_grams_mile=str(vdata.get("co2TailpipeGpm", "")),
                            annual_fuel_cost=str(vdata.get("fuelCost08", "")),
                            range_miles=str(vdata.get("range", "")),
                            cylinders=str(vdata.get("cylinders", "")),
                            displacement=str(vdata.get("displ", "")),
                            drive=str(vdata.get("drive", "")),
                            transmission=str(vdata.get("trany", "")),
                        )
                    )

            logger.info("Found %d vehicle records for %s %s %s", len(vehicles), year, make, model)

            return EpaFuelEconomyResult(
                queried_at=datetime.now(),
                make=make,
                model=model,
                year=year,
                total=len(vehicles),
                vehicles=vehicles,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "us.epa_fuel_economy", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("us.epa_fuel_economy", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("us.epa_fuel_economy", f"Fuel economy query failed: {e}") from e
