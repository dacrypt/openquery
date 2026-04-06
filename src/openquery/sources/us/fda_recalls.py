"""FDA Recalls source — US food/drug enforcement recall events.

Queries the openFDA enforcement API for recall events by product or company name.
No authentication required.

API: https://api.fda.gov/drug/enforcement.json?search=...&limit=10
"""

from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import quote

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.fda_recalls import FdaRecallEvent, FdaRecallsResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

FDA_RECALLS_URL = "https://api.fda.gov/drug/enforcement.json"


@register
class FdaRecallsSource(BaseSource):
    """Query openFDA enforcement API for drug/food recall events."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.fda_recalls",
            display_name="FDA — Drug/Food Enforcement Recalls",
            description="US FDA food and drug enforcement recalls: product, company, reason, and classification",
            country="US",
            url=FDA_RECALLS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("product_name", "")
            or input.extra.get("company", "")
            or input.document_number
        )
        if not search_term:
            raise SourceError(
                "us.fda_recalls",
                "Product name or company required (pass via extra.product_name,"
                " extra.company, or document_number)",
            )
        return self._query(search_term.strip())

    def _query(self, search_term: str) -> FdaRecallsResult:
        # Search across product description and recalling firm
        search_filter = (
            f'(product_description:"{quote(search_term)}"'
            f'+recalling_firm:"{quote(search_term)}")'
            f"+report_date:[20240101+TO+20261231]"
        )
        params = {
            "search": search_filter,
            "limit": "10",
        }

        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                resp = client.get(FDA_RECALLS_URL, params=params)
                if resp.status_code == 404:
                    # No results found is a 404 from openFDA
                    return FdaRecallsResult(
                        queried_at=datetime.now(),
                        search_term=search_term,
                        total=0,
                    )
                resp.raise_for_status()
                data = resp.json()

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "us.fda_recalls", f"FDA API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("us.fda_recalls", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("us.fda_recalls", f"Query failed: {e}") from e

        return self._parse_response(search_term, data)

    def _parse_response(self, search_term: str, data: dict) -> FdaRecallsResult:
        result = FdaRecallsResult(queried_at=datetime.now(), search_term=search_term)

        meta = data.get("meta", {}).get("results", {})
        result.total = meta.get("total", 0)

        recalls: list[FdaRecallEvent] = []
        for item in data.get("results", []):
            recalls.append(
                FdaRecallEvent(
                    product=item.get("product_description", "")[:200],
                    company=item.get("recalling_firm", ""),
                    reason=item.get("reason_for_recall", "")[:200],
                    classification=item.get("classification", ""),
                    status=item.get("status", ""),
                    date=item.get("report_date", ""),
                )
            )

        result.recalls = recalls
        return result
