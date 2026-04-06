"""US Census Bureau source — demographic and economic data.

Queries the US Census Bureau American Community Survey (ACS) API
for demographic and economic data by state or county.
Free REST API, no auth required (optional API key). Rate limit: 20 req/min.

API: https://api.census.gov/data/2020/acs/acs5
Docs: https://www.census.gov/data/developers/guidance/api-user-guide.html
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.census import CensusResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CENSUS_API_URL = "https://api.census.gov/data/2020/acs/acs5"

# Common ACS variables with friendly names
VARIABLE_LABELS: dict[str, str] = {
    "B01003_001E": "Total Population",
    "B19013_001E": "Median Household Income",
    "B25077_001E": "Median Home Value",
    "B23025_005E": "Unemployed Population",
    "B15003_022E": "Bachelor's Degree Holders",
}


@register
class CensusSource(BaseSource):
    """Query US Census Bureau ACS data by state or county."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.census",
            display_name="US Census Bureau — American Community Survey",
            description=(
                "US Census Bureau ACS 5-year estimates: population, income, "
                "housing, education by state or county"
            ),
            country="US",
            url="https://data.census.gov/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        geography = input.extra.get("geography", input.document_number).strip()
        variable = input.extra.get("variable", "B01003_001E").strip()

        if not geography:
            raise SourceError(
                "us.census",
                "Provide a state FIPS code or 'all' (extra.geography or document_number)",
            )

        return self._fetch(geography, variable)

    def _fetch(self, geography: str, variable: str) -> CensusResult:
        # Support "state:06" format or plain FIPS like "06" -> "state:06"
        if ":" not in geography and geography.lower() != "all":
            geo_param = f"state:{geography}"
        elif geography.lower() == "all":
            geo_param = "state:*"
        else:
            geo_param = geography

        params: dict[str, str] = {
            "get": f"NAME,{variable}",
            "for": geo_param,
        }

        try:
            logger.info("Querying Census ACS: geography=%s variable=%s", geography, variable)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(CENSUS_API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            # Response: [[header_row], [data_row1], ...]
            value = ""
            geo_name = geography
            details = VARIABLE_LABELS.get(variable, variable)

            if isinstance(data, list) and len(data) > 1:
                headers_row = data[0]
                # Find the variable column index
                var_idx = headers_row.index(variable) if variable in headers_row else 1
                name_idx = headers_row.index("NAME") if "NAME" in headers_row else 0

                # Aggregate or return first row
                values = []
                for row in data[1:]:
                    if len(row) > var_idx and row[var_idx] not in (None, "null", "-666666666"):
                        values.append(row[var_idx])
                    if not geo_name and len(row) > name_idx:
                        geo_name = row[name_idx]

                if values:
                    # If single row return value, else return count
                    value = values[0] if len(values) == 1 else str(len(values)) + " records"
                    if len(data) == 2:
                        geo_name = data[1][name_idx] if len(data[1]) > name_idx else geography

            return CensusResult(
                queried_at=datetime.now(),
                geography=geo_name,
                variable=variable,
                value=value,
                details=details,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "us.census", f"Census API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("us.census", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("us.census", f"Query failed: {e}") from e
