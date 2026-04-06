"""NHTSA Safety Ratings source — US NCAP crash test star ratings.

Queries the NHTSA SafetyRatings API by make, model, and model year to retrieve
NCAP crash test star ratings including overall, front crash, side crash,
rollover, and side pole ratings, plus ADAS features and safety counts.

No browser or CAPTCHA required — direct HTTP API.

API: https://api.nhtsa.gov/SafetyRatings/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.nhtsa_safety_ratings import NhtsaSafetyRating, NhtsaSafetyRatingsResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

VEHICLES_URL = "https://api.nhtsa.gov/SafetyRatings/modelyear/{year}/make/{make}/model/{model}"
RATINGS_URL = "https://api.nhtsa.gov/SafetyRatings/VehicleId/{vehicle_id}"


@register
class NhtsaSafetyRatingsSource(BaseSource):
    """Look up NHTSA NCAP crash test safety ratings by make/model/year."""

    def __init__(self, timeout: float = 20.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.nhtsa_safety_ratings",
            display_name="NHTSA — NCAP Safety Ratings",
            description="US NHTSA NCAP crash test star ratings (overall, front, side, rollover)",
            country="US",
            url="https://api.nhtsa.gov/SafetyRatings/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query NHTSA safety ratings for a given make/model/year."""
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError(
                "us.nhtsa_safety_ratings", f"Unsupported input type: {input.document_type}"
            )

        make = input.extra.get("make", "").strip()
        model = input.extra.get("model", "").strip()
        year = str(input.extra.get("year", "")).strip()

        if not make or not model or not year:
            raise SourceError(
                "us.nhtsa_safety_ratings", "make, model, and year are required in extra"
            )

        try:
            logger.info("Querying NHTSA safety ratings for %s %s %s", year, make, model)

            with httpx.Client(timeout=self._timeout) as client:
                # Step 1: get vehicle IDs for this make/model/year
                vehicles_url = VEHICLES_URL.format(year=year, make=make, model=model)
                resp = client.get(vehicles_url, params={"format": "json"})
                resp.raise_for_status()
                vehicles_data = resp.json()

            vehicle_entries = vehicles_data.get("Results", [])
            if not vehicle_entries:
                logger.info("No vehicles found for %s %s %s", year, make, model)
                return NhtsaSafetyRatingsResult(
                    queried_at=datetime.now(),
                    make=make,
                    model=model,
                    model_year=year,
                    ratings=[],
                )

            # Step 2: fetch ratings for each vehicle ID
            ratings: list[NhtsaSafetyRating] = []
            with httpx.Client(timeout=self._timeout) as client:
                for entry in vehicle_entries:
                    vehicle_id = entry.get("VehicleId")
                    vehicle_description = str(entry.get("VehicleDescription", ""))
                    if not vehicle_id:
                        continue

                    ratings_url = RATINGS_URL.format(vehicle_id=vehicle_id)
                    r = client.get(ratings_url, params={"format": "json"})
                    r.raise_for_status()
                    rdata = r.json()

                    raw = rdata.get("Results", [{}])[0] if rdata.get("Results") else {}
                    ratings.append(
                        NhtsaSafetyRating(
                            vehicle_id=vehicle_id,
                            vehicle_description=vehicle_description,
                            overall_rating=str(raw.get("OverallRating", "")),
                            front_crash_rating=str(raw.get("OverallFrontCrashRating", "")),
                            front_crash_driver_rating=str(
                                raw.get("FrontCrashDriversideRating", "")
                            ),
                            front_crash_passenger_rating=str(
                                raw.get("FrontCrashPassengersideRating", "")
                            ),
                            side_crash_rating=str(raw.get("OverallSideCrashRating", "")),
                            side_crash_driver_rating=str(raw.get("SideCrashDriversideRating", "")),
                            side_crash_passenger_rating=str(
                                raw.get("SideCrashPassengersideRating", "")
                            ),
                            rollover_rating=str(raw.get("RolloverRating", "")),
                            rollover_probability=float(raw.get("RolloverPossibility") or 0.0),
                            side_pole_rating=str(raw.get("SidePoleCrashRating", "")),
                            dynamic_tip_result=str(raw.get("dynamicTipResult", "")),
                            front_crash_picture=str(raw.get("FrontCrashPicture", "")),
                            front_crash_video=str(raw.get("FrontCrashVideo", "")),
                            side_crash_picture=str(raw.get("SideCrashPicture", "")),
                            side_crash_video=str(raw.get("SideCrashVideo", "")),
                            side_pole_picture=str(raw.get("SidePolePicture", "")),
                            side_pole_video=str(raw.get("SidePoleVideo", "")),
                            electronic_stability_control=str(
                                raw.get("NHTSAElectronicStabilityControl", "")
                            ),
                            forward_collision_warning=str(
                                raw.get("NHTSAForwardCollisionWarning", "")
                            ),
                            lane_departure_warning=str(raw.get("NHTSALaneDepartureWarning", "")),
                            complaints_count=int(raw.get("ComplaintsCount") or 0),
                            recalls_count=int(raw.get("RecallsCount") or 0),
                            investigation_count=int(raw.get("InvestigationCount") or 0),
                        )
                    )

            logger.info(
                "Found %d vehicle variant(s) with ratings for %s %s %s",
                len(ratings),
                year,
                make,
                model,
            )

            return NhtsaSafetyRatingsResult(
                queried_at=datetime.now(),
                make=make,
                model=model,
                model_year=year,
                ratings=ratings,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "us.nhtsa_safety_ratings", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("us.nhtsa_safety_ratings", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("us.nhtsa_safety_ratings", f"Safety ratings query failed: {e}") from e
