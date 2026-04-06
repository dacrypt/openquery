"""CPSC Recalls source — US product safety recalls.

Queries the CPSC (Consumer Product Safety Commission) SaferProducts
REST API for product recall information. No authentication required.

API: https://www.saferproducts.gov/RestWebServices/Recall?format=json&ProductName=
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.cpsc_recalls import CpscRecallEntry, CpscRecallsResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CPSC_API_URL = "https://www.saferproducts.gov/RestWebServices/Recall"
CPSC_URL = "https://www.saferproducts.gov/"


@register
class CpscRecallsSource(BaseSource):
    """Query CPSC SaferProducts API for product safety recalls."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.cpsc_recalls",
            display_name="CPSC — Product Safety Recalls",
            description="US Consumer Product Safety Commission recalls: product name, hazard, and recall details",  # noqa: E501
            country="US",
            url=CPSC_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("product_name", "")
            or input.document_number
        ).strip()
        if not search_term:
            raise SourceError(
                "us.cpsc_recalls",
                "Product name required (pass via extra.product_name or document_number)",
            )
        return self._query(search_term)

    def _query(self, search_term: str) -> CpscRecallsResult:
        params = {
            "format": "json",
            "ProductName": search_term,
        }

        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                resp = client.get(CPSC_API_URL, params=params)
                if resp.status_code == 404:
                    return CpscRecallsResult(
                        queried_at=datetime.now(),
                        search_term=search_term,
                        total=0,
                    )
                resp.raise_for_status()
                data = resp.json()

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "us.cpsc_recalls", f"CPSC API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("us.cpsc_recalls", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("us.cpsc_recalls", f"Query failed: {e}") from e

        return self._parse_response(search_term, data)

    def _parse_response(self, search_term: str, data: list) -> CpscRecallsResult:
        result = CpscRecallsResult(queried_at=datetime.now(), search_term=search_term)

        recalls: list[CpscRecallEntry] = []
        items = data if isinstance(data, list) else data.get("recalls", [])
        for item in items[:20]:
            recalls.append(
                CpscRecallEntry(
                    title=item.get("Title", item.get("Name", ""))[:200],
                    description=item.get("Description", item.get("Hazard", ""))[:300],
                    date=item.get("RecallDate", item.get("Date", "")),
                )
            )

        result.recalls = recalls
        result.total = len(recalls)
        return result
