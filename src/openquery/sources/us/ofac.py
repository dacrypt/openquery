"""OFAC SDN List source — US Treasury sanctions screening.

Queries the OFAC Specially Designated Nationals (SDN) list to check
if a person or entity appears on US sanctions lists.

Uses the OFAC sanctions search API for name-based lookups.
No browser or CAPTCHA required — direct HTTP.

API: https://sanctionssearch.ofac.treas.gov/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.ofac import OfacEntry, OfacResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

OFAC_SEARCH_URL = "https://sanctionssearch.ofac.treas.gov/"
OFAC_SDN_XML_URL = "https://www.treasury.gov/ofac/downloads/sdn.xml"
OFAC_API_URL = "https://search.ofac-sdn.treas.gov/search"


@register
class OfacSource(BaseSource):
    """Screen names/entities against the OFAC SDN sanctions list."""

    def __init__(self, timeout: float = 15.0, min_score: float = 80.0) -> None:
        self._timeout = timeout
        self._min_score = min_score

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.ofac",
            display_name="OFAC — US Treasury Sanctions (SDN List)",
            description="US Treasury OFAC Specially Designated Nationals (SDN) sanctions screening",
            country="US",
            url=OFAC_SEARCH_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.NIT, DocumentType.PASSPORT, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        name = input.extra.get("name", "").strip()
        doc_number = input.document_number.strip()

        if not name and not doc_number:
            raise SourceError("us.ofac", "Provide a name (extra.name) or document number to search")

        search_term = name if name else doc_number
        return self._search(search_term)

    def _search(self, query: str) -> OfacResult:
        try:
            with httpx.Client(timeout=self._timeout, verify=True) as client:
                resp = client.get(
                    OFAC_API_URL,
                    params={"q": query, "score": int(self._min_score)},
                    headers={"Accept": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()

            matches = []
            results = data if isinstance(data, list) else data.get("results", [])

            for entry in results:
                score = float(entry.get("score", 0))
                if score < self._min_score:
                    continue
                matches.append(OfacEntry(
                    uid=str(entry.get("uid", "")),
                    name=entry.get("name", ""),
                    type=entry.get("type", ""),
                    programs=entry.get("programs", []),
                    remarks=entry.get("remarks", ""),
                    score=score,
                ))

            return OfacResult(
                queried_at=datetime.now(),
                query=query,
                match_count=len(matches),
                is_sanctioned=len(matches) > 0,
                matches=matches,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("us.ofac", f"OFAC API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("us.ofac", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("us.ofac", f"OFAC search failed: {e}") from e
