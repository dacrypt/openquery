"""IDB (Inter-American Development Bank) data source.

Queries the IDB DataBank REST API for Latin America development indicators.
Free REST API, no auth, no CAPTCHA. Rate limit: 10 req/min.

API: https://data.iadb.org/
Docs: https://data.iadb.org/DataCatalog/Dataset
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.idb import IdbDataPoint, IdbResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_BASE_URL = "https://data.iadb.org/api/indicators/{indicator}/countries/{country}"


@register
class IdbSource(BaseSource):
    """Query IDB Latin America development indicators."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.idb",
            display_name="IDB — Inter-American Development Bank Data",
            description=(
                "IDB DataBank: development indicators for Latin America and the Caribbean"
            ),
            country="INTL",
            url="https://data.iadb.org/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        country = input.extra.get("country", input.document_number).strip().upper()
        indicator = input.extra.get("indicator", "").strip()

        if not country:
            raise SourceError(
                "intl.idb",
                "Provide a country ISO2 code (extra.country or document_number)",
            )
        if not indicator:
            raise SourceError(
                "intl.idb",
                "Provide an indicator code (extra.indicator), e.g. BI.POV.DDAY",
            )

        return self._fetch(country, indicator)

    def _fetch(self, country: str, indicator: str) -> IdbResult:
        url = API_BASE_URL.format(indicator=indicator, country=country)

        try:
            logger.info("Querying IDB: country=%s indicator=%s", country, indicator)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(url, params={"format": "json"})
                resp.raise_for_status()
                data = resp.json()

            data_points: list[IdbDataPoint] = []
            details = ""

            # IDB API returns list of {year, value, ...} objects
            records = data if isinstance(data, list) else data.get("data", [])
            indicator_name = ""
            for record in records:
                if not indicator_name:
                    indicator_name = record.get("indicatorName", "") or record.get(
                        "indicator_name", ""
                    )
                year = str(record.get("year", record.get("date", "")))
                raw_val = record.get("value")
                value_str = str(raw_val) if raw_val is not None else ""
                if year:
                    data_points.append(IdbDataPoint(year=year, value=value_str))

            if indicator_name:
                details = indicator_name

            return IdbResult(
                queried_at=datetime.now(),
                country_code=country,
                indicator=indicator,
                data_points=data_points,
                details=details,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "intl.idb", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("intl.idb", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.idb", f"Query failed: {e}") from e
