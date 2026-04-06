"""EPA TRIS source — US Toxics Release Inventory.

Queries the EPA TRIS (Toxics Release Inventory System) for facility
toxic release data. No authentication required.

API: https://enviro.epa.gov/enviro/efservice/TRI_FACILITY/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.epa_tris import EpaTrisResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

EPA_TRIS_API_URL = "https://enviro.epa.gov/enviro/efservice/TRI_FACILITY"
EPA_URL = "https://enviro.epa.gov/"


@register
class EpaTrisSource(BaseSource):
    """Query EPA Toxics Release Inventory for facility data."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.epa_tris",
            display_name="EPA — Toxics Release Inventory (TRI)",
            description="EPA Toxics Release Inventory: facilities releasing toxic chemicals by name or state",  # noqa: E501
            country="US",
            url=EPA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("facility_name", "")
            or input.extra.get("state", "")
            or input.document_number
        ).strip()
        if not search_term:
            raise SourceError(
                "us.epa_tris",
                "Facility name or state required (pass via extra.facility_name, extra.state, or document_number)",  # noqa: E501
            )
        search_type = "state" if (len(search_term) == 2 and search_term.isalpha()) else "facility"
        return self._query(search_term, search_type)

    def _query(self, search_term: str, search_type: str = "facility") -> EpaTrisResult:
        if search_type == "state":
            url = f"{EPA_TRIS_API_URL}/ST_ABBR/{search_term.upper()}/JSON"
        else:
            url = f"{EPA_TRIS_API_URL}/FAC_NAME/CONTAINING/{search_term.upper()}/JSON"

        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code == 404:
                    return EpaTrisResult(
                        queried_at=datetime.now(),
                        search_term=search_term,
                        total_facilities=0,
                    )
                resp.raise_for_status()
                data = resp.json()

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "us.epa_tris", f"EPA TRI API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("us.epa_tris", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("us.epa_tris", f"Query failed: {e}") from e

        return self._parse_response(search_term, data)

    def _parse_response(self, search_term: str, data: list | dict) -> EpaTrisResult:
        result = EpaTrisResult(queried_at=datetime.now(), search_term=search_term)

        items = data if isinstance(data, list) else [data]
        facilities = []
        for item in items[:20]:
            facilities.append({
                "facility_name": item.get("FAC_NAME", ""),
                "city": item.get("CITY_NAME", ""),
                "state": item.get("ST_ABBR", ""),
                "zip": item.get("ZIP_CODE", ""),
            })

        result.facilities = facilities
        result.total_facilities = len(facilities)
        return result
