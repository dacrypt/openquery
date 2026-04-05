"""NHTSA Investigations source — US NHTSA ODI defect investigations.

Queries the NHTSA ODI investigations API by make, model, and year to retrieve
defect investigations including type, status, subject, and components affected.

No browser or CAPTCHA required — direct HTTP API.

API: https://api.nhtsa.gov/investigations
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.nhtsa_investigations import NhtsaInvestigation, NhtsaInvestigationsResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://api.nhtsa.gov/investigations"

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return _HTML_TAG_RE.sub("", text).strip()


@register
class NhtsaInvestigationsSource(BaseSource):
    """Look up NHTSA ODI defect investigations by make/model/year."""

    def __init__(self, timeout: float = 20.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.nhtsa_investigations",
            display_name="NHTSA — Defect Investigations",
            description="US NHTSA ODI defect investigations by vehicle make/model/year",
            country="US",
            url="https://api.nhtsa.gov/investigations",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query NHTSA ODI investigations for a given make/model/year."""
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError(
                "us.nhtsa_investigations", f"Unsupported input type: {input.document_type}"
            )

        make = input.extra.get("make", "").strip()
        model = input.extra.get("model", "").strip()
        year = str(input.extra.get("year", "")).strip()

        if not make or not model or not year:
            raise SourceError(
                "us.nhtsa_investigations", "make, model, and year are required in extra"
            )

        try:
            logger.info("Querying NHTSA investigations for %s %s %s", year, make, model)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(
                    API_URL,
                    params={
                        "make": make,
                        "model": model,
                        "fromYear": year,
                        "toYear": year,
                        "format": "json",
                        "max": 50,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            raw_results = data.get("results", [])
            total = data.get("meta", {}).get("pagination", {}).get("total", len(raw_results))

            investigations: list[NhtsaInvestigation] = []
            for entry in raw_results:
                components_raw = entry.get("components", [])
                if isinstance(components_raw, list):
                    components = [str(c) for c in components_raw if c]
                else:
                    components = [str(components_raw)] if components_raw else []

                investigations.append(
                    NhtsaInvestigation(
                        nhtsa_id=str(entry.get("nhtsaId", "") or ""),
                        investigation_number=str(entry.get("investigationNumber", "") or ""),
                        investigation_type=str(entry.get("investigationType", "") or ""),
                        subject=str(entry.get("subject", "") or ""),
                        description=_strip_html(str(entry.get("description", "") or "")),
                        status=str(entry.get("status", "") or ""),
                        open_date=str(entry.get("openDate", "") or ""),
                        close_date=str(entry.get("closeDate", "") or ""),
                        components=components,
                        make=str(entry.get("make", "") or ""),
                        model=str(entry.get("model", "") or ""),
                        year=str(entry.get("year", "") or ""),
                    )
                )

            logger.info(
                "Found %d investigations for %s %s %s", len(investigations), year, make, model
            )

            return NhtsaInvestigationsResult(
                queried_at=datetime.now(),
                make=make,
                model=model,
                model_year=year,
                total=total,
                investigations=investigations,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "us.nhtsa_investigations", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("us.nhtsa_investigations", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("us.nhtsa_investigations", f"Investigations query failed: {e}") from e
