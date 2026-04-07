"""OICA global vehicle production/sales source.

Queries the jhelvy/oica GitHub CSV mirror of OICA global vehicle
production and sales data by country and year.

Data mirror: https://raw.githubusercontent.com/jhelvy/oicadata/main/data/sales.csv
Original: https://oica.net/sales-statistics/

No auth required. Rate limit: 10 req/min (GitHub raw).
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.oica import OicaCountryData, OicaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

# jhelvy/oicadata CSV mirror on GitHub
OICA_CSV_URL = "https://raw.githubusercontent.com/jhelvy/oicadata/main/data/sales.csv"

# Fallback production CSV
OICA_PROD_CSV_URL = "https://raw.githubusercontent.com/jhelvy/oicadata/main/data/production.csv"


@register
class OicaSource(BaseSource):
    """Query OICA global vehicle production/sales statistics."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.oica",
            display_name="OICA — Global Vehicle Production & Sales",
            description=(
                "OICA (Organisation Internationale des Constructeurs d'Automobiles) "
                "global vehicle production and sales data by country and year"
            ),
            country="INTL",
            url="https://oica.net/sales-statistics/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        country_filter = input.extra.get("country", input.document_number or "").strip().upper()
        year_filter = input.extra.get("year", "").strip()
        search_term = " | ".join(filter(None, [country_filter, year_filter])) or "all"
        return self._fetch(country_filter, year_filter, search_term)

    def _fetch(self, country_filter: str, year_filter: str, search_term: str) -> OicaResult:
        try:
            logger.info(
                "Querying OICA: country=%s year=%s", country_filter or "all", year_filter or "all"
            )

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "text/csv, text/plain, */*",
            }

            with httpx.Client(
                timeout=self._timeout, headers=headers, follow_redirects=True
            ) as client:
                resp = client.get(OICA_CSV_URL)
                resp.raise_for_status()
                csv_content = resp.text

            return self._parse_csv(csv_content, country_filter, year_filter, search_term)

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "intl.oica", f"HTTP {e.response.status_code} fetching OICA data"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("intl.oica", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.oica", f"Query failed: {e}") from e

    def _parse_csv(
        self, csv_content: str, country_filter: str, year_filter: str, search_term: str
    ) -> OicaResult:
        data: list[OicaCountryData] = []
        countries_seen: set[str] = set()

        reader = csv.DictReader(io.StringIO(csv_content))
        for row in reader:
            norm = {k.lower().strip(): (v or "").strip() for k, v in row.items()}

            country = _extract_field(norm, ["country", "region", "pays"])
            year = _extract_field(norm, ["year", "annee", "ano"])

            # Apply filters
            if country_filter and country.upper() != country_filter:
                # Also try partial match
                if country_filter not in country.upper():
                    continue
            if year_filter and year != year_filter:
                continue

            passenger = _safe_int(
                _extract_field(norm, ["passenger_cars", "passenger", "cars", "voitures"])
            )
            commercial = _safe_int(
                _extract_field(norm, ["commercial_vehicles", "commercial", "trucks", "utilitaires"])
            )
            total_raw = _extract_field(norm, ["total", "total_vehicles"])
            total = _safe_int(total_raw) if total_raw else passenger + commercial

            data.append(
                OicaCountryData(
                    country=country,
                    year=year,
                    passenger_cars=passenger,
                    commercial_vehicles=commercial,
                    total=total,
                )
            )
            countries_seen.add(country)

        return OicaResult(
            queried_at=datetime.now(),
            search_term=search_term,
            total_countries=len(countries_seen),
            data=data,
        )


def _extract_field(norm: dict[str, str], candidates: list[str]) -> str:
    """Extract first matching field from normalized row dict."""
    for key in candidates:
        if key in norm:
            return norm[key]
    return ""


def _safe_int(val: str) -> int:
    """Safely convert string to int, handling commas and whitespace."""
    if not val:
        return 0
    try:
        return int(float(val.replace(",", "").replace(" ", "").strip()))
    except (ValueError, TypeError):
        return 0
