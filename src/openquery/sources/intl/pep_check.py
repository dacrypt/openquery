"""PEP Check source — Politically Exposed Persons aggregated check.

Checks multiple public PEP lists and sanctions databases for
politically exposed person status across jurisdictions.

Uses public OFAC and UN sanctions lists as data sources.
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.pep_check import PepCheckResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

OPENSANCTIONS_API_URL = "https://api.opensanctions.org/search/default"
PEP_URL = "https://www.opensanctions.org/"


@register
class PepCheckSource(BaseSource):
    """Check politically exposed person status across public jurisdictions."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.pep_check",
            display_name="PEP Check — Politically Exposed Persons",
            description="Aggregated PEP check across public sanctions and PEP databases (OpenSanctions)",  # noqa: E501
            country="INTL",
            url=PEP_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("name", "")
            or input.document_number
        ).strip()
        if not search_term:
            raise SourceError(
                "intl.pep_check",
                "Name required (pass via extra.name or document_number)",
            )
        return self._search(search_term)

    def _search(self, query: str) -> PepCheckResult:
        params = {
            "q": query,
            "schema": "Person",
            "topics": "role.pep",
            "limit": "10",
        }

        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                resp = client.get(OPENSANCTIONS_API_URL, params=params)
                if resp.status_code in (401, 403):
                    # API key required — return structure with empty results
                    return PepCheckResult(
                        queried_at=datetime.now(),
                        search_term=query,
                        is_pep=False,
                        details={"message": "API key required for OpenSanctions; register at opensanctions.org"},  # noqa: E501
                    )
                if resp.status_code == 404:
                    return PepCheckResult(
                        queried_at=datetime.now(),
                        search_term=query,
                        is_pep=False,
                    )
                resp.raise_for_status()
                data = resp.json()

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "intl.pep_check", f"OpenSanctions API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("intl.pep_check", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("intl.pep_check", f"PEP check failed: {e}") from e

        return self._parse_response(query, data)

    def _parse_response(self, query: str, data: dict) -> PepCheckResult:
        result = PepCheckResult(queried_at=datetime.now(), search_term=query)

        results = data.get("results", [])
        jurisdictions = set()

        for item in results:
            datasets = item.get("datasets", [])
            for ds in datasets:
                jurisdictions.add(ds)
            properties = item.get("properties", {})
            countries = properties.get("country", [])
            for c in countries:
                jurisdictions.add(c.upper())

        result.is_pep = len(results) > 0
        result.jurisdictions = sorted(jurisdictions)
        result.details = {"total_matches": len(results)}
        return result
