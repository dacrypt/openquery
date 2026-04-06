"""Lista Clinton source — Colombia SDN/OFAC sanctions list check.

Queries OFAC SDN list (via public API) for Colombia-linked sanctions.

Flow:
1. Query OFAC SDN API with search term
2. Parse result for listing status, list type

Source: https://www.treasury.gov/ofac/downloads/sdn.xml (public OFAC data)
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.lista_clinton import ListaClintonResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

OFAC_API_URL = "https://ofac-api.com/search"
OFAC_FALLBACK_URL = "https://sanctionssearch.ofac.treas.gov/"


@register
class ListaClintonSource(BaseSource):
    """Query Colombia Clinton List / OFAC SDN sanctions check."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.lista_clinton",
            display_name="Lista Clinton — OFAC/SDN Colombia",
            description="Colombia Clinton List check — OFAC SDN sanctions list",
            country="CO",
            url=OFAC_FALLBACK_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("name") or input.document_number
        if not search_term:
            raise SourceError("co.lista_clinton", "name is required")
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> ListaClintonResult:
        import httpx

        try:
            resp = httpx.get(
                "https://sanctionssearch.ofac.treas.gov/SdnSearch.aspx",
                params={"search": search_term},
                timeout=self._timeout,
                follow_redirects=True,
            )
            body_lower = resp.text.lower()
        except Exception as e:
            raise SourceError("co.lista_clinton", f"Request failed: {e}") from e

        is_listed = any(
            phrase in body_lower
            for phrase in ["sdn list", "specially designated", "found", "match"]
        )

        no_results = any(
            phrase in body_lower
            for phrase in ["no results", "no match", "0 results", "not found"]
        )

        if no_results:
            is_listed = False

        list_type = "SDN" if is_listed else ""

        from datetime import datetime

        return ListaClintonResult(
            queried_at=datetime.now(),
            search_term=search_term,
            is_listed=is_listed,
            list_type=list_type,
            details={"source": "OFAC SDN"},
        )
