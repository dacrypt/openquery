"""Basel AML Index source — country AML risk scores.

Queries the Basel Institute on Governance AML Index for
country-level anti-money laundering risk scores.

Source: https://index.baselgovernance.org/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.basel_aml import BaselAmlResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

BASEL_AML_URL = "https://index.baselgovernance.org/"
BASEL_API_URL = "https://index.baselgovernance.org/api/scores"


@register
class BaselAmlSource(BaseSource):
    """Query Basel AML Index for country AML risk scores."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.basel_aml",
            display_name="Basel AML Index",
            description="Basel Institute AML Index: country-level anti-money laundering risk scores and rankings",  # noqa: E501
            country="INTL",
            url=BASEL_AML_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        country = (
            input.extra.get("country", "")
            or input.document_number
        ).strip()
        if not country:
            raise SourceError(
                "intl.basel_aml",
                "Country name or code required (pass via extra.country or document_number)",
            )
        return self._query(country)

    def _query(self, country: str) -> BaselAmlResult:
        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                resp = client.get(BASEL_API_URL)
                if resp.status_code == 404:
                    return BaselAmlResult(
                        queried_at=datetime.now(),
                        country=country,
                        details={"message": "No data available"},
                    )
                resp.raise_for_status()
                data = resp.json()

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "intl.basel_aml", f"Basel AML API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("intl.basel_aml", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("intl.basel_aml", f"Query failed: {e}") from e

        return self._parse_response(country, data)

    def _parse_response(self, country: str, data: list | dict) -> BaselAmlResult:
        result = BaselAmlResult(queried_at=datetime.now(), country=country)

        items = data if isinstance(data, list) else data.get("data", data.get("scores", []))
        country_lower = country.lower()

        for rank, item in enumerate(items, 1):
            name = item.get("country", item.get("name", item.get("Country", ""))).lower()
            code = item.get("iso", item.get("code", item.get("ISO", ""))).lower()
            if country_lower in name or country_lower == code:
                result.aml_score = float(item.get("score", item.get("Score", item.get("value", 0))))
                result.aml_rank = item.get("rank", item.get("Rank", rank))
                result.details = {k: v for k, v in item.items() if k not in ("score", "rank")}
                break

        return result
