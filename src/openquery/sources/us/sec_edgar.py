"""SEC EDGAR source — US company filings search.

Queries SEC EDGAR's full-text search API for company filings (10-K, 10-Q, 8-K).
No authentication required.

API: https://efts.sec.gov/LATEST/search-index?q={query}&forms=10-K,10-Q,8-K
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.sec_edgar import SecEdgarFiling, SecEdgarResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SEC_EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
SEC_EDGAR_FILING_URL = "https://www.sec.gov/cgi-bin/browse-edgar"


@register
class SecEdgarSource(BaseSource):
    """Query SEC EDGAR for company filings by name or CIK."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.sec_edgar",
            display_name="SEC EDGAR — Company Filings",
            description="SEC EDGAR company filing search: 10-K, 10-Q, 8-K by company name or CIK",
            country="US",
            url=SEC_EDGAR_SEARCH_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("company_name", "")
            or input.extra.get("cik", "")
            or input.document_number
        )
        if not search_term:
            raise SourceError(
                "us.sec_edgar",
                "Company name or CIK required (pass via extra.company_name, extra.cik,"
                " or document_number)",
            )
        return self._query(search_term.strip())

    def _query(self, search_term: str) -> SecEdgarResult:
        params = {
            "q": search_term,
            "forms": "10-K,10-Q,8-K",
            "dateRange": "custom",
            "startdt": "2024-01-01",
            "enddt": "2026-12-31",
        }

        try:
            with httpx.Client(
                timeout=self._timeout,
                follow_redirects=True,
                headers={"User-Agent": "openquery/1.0 research@example.com"},
            ) as client:
                resp = client.get(SEC_EDGAR_SEARCH_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "us.sec_edgar", f"SEC EDGAR API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("us.sec_edgar", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("us.sec_edgar", f"Query failed: {e}") from e

        return self._parse_response(search_term, data)

    def _parse_response(self, search_term: str, data: dict) -> SecEdgarResult:
        result = SecEdgarResult(queried_at=datetime.now(), search_term=search_term)

        hits = data.get("hits", {})
        total_val = hits.get("total", {})
        if isinstance(total_val, dict):
            result.total_filings = total_val.get("value", 0)
        elif isinstance(total_val, int):
            result.total_filings = total_val

        filings: list[SecEdgarFiling] = []
        for hit in hits.get("hits", []):
            src = hit.get("_source", {})
            # Extract company name and CIK from first filing
            if not result.company_name:
                display_names = src.get("display_names", [])
                result.company_name = (
                    src.get("entity_name", "")
                    or (display_names[0] if display_names else "")
                )
            if not result.cik:
                result.cik = src.get("entity_id", "") or src.get("file_num", "")

            filings.append(
                SecEdgarFiling(
                    filing_type=src.get("file_type", "") or src.get("form_type", ""),
                    date=src.get("file_date", "") or src.get("period_of_report", ""),
                    description=src.get("description", "") or src.get("form_type", ""),
                    url=src.get("_id", ""),
                )
            )

        result.filings = filings
        return result
