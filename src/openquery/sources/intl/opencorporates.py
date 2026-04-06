"""OpenCorporates global company search source.

Queries the OpenCorporates public API for company information worldwide.
Unauthenticated: 500 req/month. Authenticated: higher limits.

API: https://api.opencorporates.com/v0.4/companies/search
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.opencorporates import IntlOpenCorporatesResult, OpenCorporatesCompany
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

OC_API_URL = "https://api.opencorporates.com/v0.4/companies/search"


@register
class IntlOpenCorporatesSource(BaseSource):
    """Search global company data via OpenCorporates."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.opencorporates",
            display_name="OpenCorporates — Global Company Search",
            description="OpenCorporates: company search across 140+ jurisdictions worldwide",
            country="INTL",
            url="https://opencorporates.com/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=5,
        )

    def query(self, input: QueryInput) -> BaseModel:
        name = (input.extra.get("name", "") or input.document_number).strip()
        if not name:
            raise SourceError(
                "intl.opencorporates", "Provide a company name (extra.name) or document number"
            )

        jurisdiction = input.extra.get("jurisdiction", "").strip()
        return self._search(name, jurisdiction)

    def _search(self, name: str, jurisdiction: str = "") -> IntlOpenCorporatesResult:
        try:
            logger.info("Searching OpenCorporates: %s", name)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }

            params: dict[str, str | int] = {
                "q": name,
                "per_page": 10,
                "page": 1,
            }
            if jurisdiction:
                params["jurisdiction_code"] = jurisdiction.lower()

            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(OC_API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            api_results = data.get("results", {})
            total_count = api_results.get("total_count", 0)
            raw_companies = api_results.get("companies", [])

            companies: list[OpenCorporatesCompany] = []
            for item in raw_companies:
                co = item.get("company", item)
                addr = co.get("registered_address", {})
                if isinstance(addr, dict):
                    addr_str = ", ".join(
                        filter(
                            None,
                            [
                                addr.get("street_address", ""),
                                addr.get("locality", ""),
                                addr.get("country", ""),
                            ],
                        )
                    )
                else:
                    addr_str = str(addr) if addr else ""

                companies.append(
                    OpenCorporatesCompany(
                        name=co.get("name", ""),
                        jurisdiction=co.get("jurisdiction_code", ""),
                        status=co.get("current_status", "") or co.get("company_status", ""),
                        company_number=co.get("company_number", ""),
                        incorporation_date=co.get("incorporation_date", "") or "",
                        company_type=co.get("company_type", "") or "",
                        registered_address=addr_str,
                    )
                )

            return IntlOpenCorporatesResult(
                queried_at=datetime.now(),
                search_term=name,
                total=total_count,
                companies=companies,
            )

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 429:
                raise SourceError(
                    "intl.opencorporates", "Rate limit exceeded (500 req/month unauthenticated)"
                ) from e
            raise SourceError("intl.opencorporates", f"API returned HTTP {status}") from e
        except httpx.RequestError as e:
            raise SourceError("intl.opencorporates", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.opencorporates", f"Query failed: {e}") from e
