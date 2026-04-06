"""Global Terrorism Database source — terrorism incident data.

Queries the START Center's Global Terrorism Database (GTD)
for terrorism incident data by country or keyword search.

Note: GTD data is available via the START center's public APIs.
Source: https://www.start.umd.edu/gtd/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.global_terrorism import GlobalTerrorismResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

GTD_URL = "https://www.start.umd.edu/gtd/"
# Public UNODC data as fallback for terrorism-related stats
UNODC_API_URL = "https://dataunodc.un.org/api/data/terrorism"


@register
class GlobalTerrorismSource(BaseSource):
    """Query Global Terrorism Database for terrorism incident data."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.global_terrorism",
            display_name="GTD — Global Terrorism Database",
            description="Global Terrorism Database: terrorism incidents by country or keyword (START Center/UNODC)",  # noqa: E501
            country="INTL",
            url=GTD_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("country", "")
            or input.extra.get("search", "")
            or input.document_number
        ).strip()
        if not search_term:
            raise SourceError(
                "intl.global_terrorism",
                "Country or search term required (pass via extra.country, extra.search, or document_number)",  # noqa: E501
            )
        return self._query(search_term)

    def _query(self, search_term: str) -> GlobalTerrorismResult:
        # Use UNODC public terrorism stats API
        params = {
            "country": search_term,
            "format": "json",
        }

        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                resp = client.get(UNODC_API_URL, params=params)
                if resp.status_code in (404, 400):
                    return GlobalTerrorismResult(
                        queried_at=datetime.now(),
                        search_term=search_term,
                        total_incidents=0,
                        details={"message": "No terrorism data found for this search term"},
                    )
                resp.raise_for_status()
                data = resp.json()

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "intl.global_terrorism", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("intl.global_terrorism", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("intl.global_terrorism", f"Query failed: {e}") from e

        return self._parse_response(search_term, data)

    def _parse_response(self, search_term: str, data: list | dict) -> GlobalTerrorismResult:
        result = GlobalTerrorismResult(queried_at=datetime.now(), search_term=search_term)

        items = data if isinstance(data, list) else data.get("data", data.get("results", []))
        incidents = []
        for item in items[:20]:
            incidents.append({
                "country": item.get("country", item.get("Country", "")),
                "year": str(item.get("year", item.get("Year", ""))),
                "incidents": item.get("incidents", item.get("Incidents", item.get("value", ""))),
            })

        result.incidents = incidents
        result.total_incidents = len(incidents)
        return result
