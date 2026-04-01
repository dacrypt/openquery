"""NHTSA Recalls source — US vehicle safety recall campaigns.

Queries the NHTSA recalls API by make, model, and model year to retrieve
safety recall campaigns including component, summary, consequence, and remedy.

No browser or CAPTCHA required — direct HTTP API.

API: https://api.nhtsa.gov/recalls/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.nhtsa_recalls import NhtsaRecall, NhtsaRecallsResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://api.nhtsa.gov/recalls/recallsByVehicle"


@register
class NhtsaRecallsSource(BaseSource):
    """Look up NHTSA vehicle safety recalls by make/model/year."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.nhtsa_recalls",
            display_name="NHTSA — Vehicle Recalls",
            description="US NHTSA vehicle safety recall campaigns",
            country="US",
            url="https://api.nhtsa.gov/recalls/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query NHTSA recalls for a given make/model/year."""
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("us.nhtsa_recalls", f"Unsupported input type: {input.document_type}")

        make = input.extra.get("make", "").strip()
        model = input.extra.get("model", "").strip()
        year = str(input.extra.get("year", "")).strip()

        if not make or not model or not year:
            raise SourceError("us.nhtsa_recalls", "make, model, and year are required in extra")

        try:
            logger.info("Querying NHTSA recalls for %s %s %s", year, make, model)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(
                    API_URL,
                    params={"make": make, "model": model, "modelYear": year},
                )
                resp.raise_for_status()
                data = resp.json()

            raw_results = data.get("results", [])
            recalls: list[NhtsaRecall] = []
            for entry in raw_results:
                recalls.append(NhtsaRecall(
                    campaign_number=str(entry.get("NHTSACampaignNumber", "")),
                    date_reported=str(entry.get("ReportReceivedDate", "")),
                    component=str(entry.get("Component", "")),
                    summary=str(entry.get("Summary", "")),
                    consequence=str(entry.get("Consequence", "")),
                    remedy=str(entry.get("Remedy", "")),
                    manufacturer=str(entry.get("Manufacturer", "")),
                    notes=str(entry.get("Notes", "")),
                ))

            logger.info("Found %d recalls for %s %s %s", len(recalls), year, make, model)

            return NhtsaRecallsResult(
                queried_at=datetime.now(),
                make=make,
                model=model,
                model_year=year,
                total_recalls=len(recalls),
                recalls=recalls,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("us.nhtsa_recalls", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("us.nhtsa_recalls", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("us.nhtsa_recalls", f"Recalls query failed: {e}") from e
