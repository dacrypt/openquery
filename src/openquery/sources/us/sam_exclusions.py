"""SAM.gov Exclusions source — US debarment and excluded parties list.

Queries SAM.gov's exclusions API for debarred or suspended entities.
Uses DEMO_KEY for limited public access (no registration required).

API: https://api.sam.gov/entity-information/v3/exclusions?api_key=DEMO_KEY&q={name}
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.sam_exclusions import SamExclusion, SamExclusionsResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SAM_EXCLUSIONS_URL = "https://api.sam.gov/entity-information/v3/exclusions"


@register
class SamExclusionsSource(BaseSource):
    """Query SAM.gov exclusions API for debarred or suspended parties."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.sam_exclusions",
            display_name="SAM.gov — Excluded Parties (Debarment)",
            description=(
                "US SAM.gov excluded parties list: debarred or suspended persons/entities"
                " from federal contracting"
            ),
            country="US",
            url=SAM_EXCLUSIONS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("name", "") or input.extra.get("company", "") or input.document_number
        )
        if not search_term:
            raise SourceError(
                "us.sam_exclusions",
                "Person or company name required (pass via extra.name, extra.company,"
                " or document_number)",
            )
        return self._query(search_term.strip())

    def _query(self, search_term: str) -> SamExclusionsResult:
        from openquery.config import get_settings

        api_key = get_settings().sam_api_key or "DEMO_KEY"

        params = {
            "api_key": api_key,
            "q": search_term,
            "limit": "10",
        }

        try:
            with httpx.Client(
                timeout=self._timeout,
                follow_redirects=True,
                headers={"Accept": "application/json"},
            ) as client:
                resp = client.get(SAM_EXCLUSIONS_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "us.sam_exclusions",
                f"SAM.gov API returned HTTP {e.response.status_code}",
            ) from e
        except httpx.RequestError as e:
            raise SourceError("us.sam_exclusions", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("us.sam_exclusions", f"Query failed: {e}") from e

        return self._parse_response(search_term, data)

    def _parse_response(self, search_term: str, data: dict) -> SamExclusionsResult:
        result = SamExclusionsResult(queried_at=datetime.now(), search_term=search_term)

        result.total = data.get("totalRecords", 0)

        exclusions: list[SamExclusion] = []
        for item in data.get("exclusionData", []):
            entity = item.get("entityInformation", {})
            excl = item.get("exclusionDetails", {})
            exclusions.append(
                SamExclusion(
                    name=entity.get("entityName", "") or entity.get("legalBusinessName", ""),
                    entity_type=entity.get("entityType", ""),
                    exclusion_type=excl.get("exclusionType", ""),
                    agency=excl.get("agencyName", "") or excl.get("ctCode", ""),
                    date=excl.get("activationDate", "") or excl.get("creationDate", ""),
                )
            )

        result.exclusions = exclusions
        return result
