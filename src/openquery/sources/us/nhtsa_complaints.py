"""NHTSA Complaints source — US consumer vehicle safety complaints.

Queries the NHTSA complaints API by make, model, and model year to retrieve
consumer-reported safety complaints including crash/fire flags and injury data.

No browser or CAPTCHA required — direct HTTP API.

API: https://api.nhtsa.gov/complaints/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.nhtsa_complaints import NhtsaComplaint, NhtsaComplaintsResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://api.nhtsa.gov/complaints/complaintsByVehicle"


@register
class NhtsaComplaintsSource(BaseSource):
    """Look up NHTSA consumer vehicle safety complaints by make/model/year."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.nhtsa_complaints",
            display_name="NHTSA — Vehicle Complaints",
            description="US NHTSA consumer vehicle safety complaints",
            country="US",
            url="https://api.nhtsa.gov/complaints/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query NHTSA complaints for a given make/model/year."""
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("us.nhtsa_complaints", f"Unsupported input type: {input.document_type}")

        make = input.extra.get("make", "").strip()
        model = input.extra.get("model", "").strip()
        year = str(input.extra.get("year", "")).strip()

        if not make or not model or not year:
            raise SourceError("us.nhtsa_complaints", "make, model, and year are required in extra")

        try:
            logger.info("Querying NHTSA complaints for %s %s %s", year, make, model)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(
                    API_URL,
                    params={"make": make, "model": model, "modelYear": year},
                )
                resp.raise_for_status()
                data = resp.json()

            raw_results = data.get("results", [])
            complaints: list[NhtsaComplaint] = []
            for entry in raw_results:
                complaints.append(NhtsaComplaint(
                    odi_number=str(entry.get("odiNumber", "")),
                    date_complaint=str(entry.get("dateComplaintFiled", "")),
                    component=str(entry.get("components", "")),
                    summary=str(entry.get("summary", "")),
                    crash=bool(entry.get("crash", False)),
                    fire=bool(entry.get("fire", False)),
                    injuries=int(entry.get("numberOfInjuries", 0) or 0),
                    deaths=int(entry.get("numberOfDeaths", 0) or 0),
                ))

            logger.info("Found %d complaints for %s %s %s", len(complaints), year, make, model)

            return NhtsaComplaintsResult(
                queried_at=datetime.now(),
                make=make,
                model=model,
                model_year=year,
                total_complaints=len(complaints),
                complaints=complaints,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("us.nhtsa_complaints", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("us.nhtsa_complaints", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("us.nhtsa_complaints", f"Complaints query failed: {e}") from e
