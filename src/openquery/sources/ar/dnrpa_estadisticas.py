"""DNRPA vehicle registration statistics source — Argentina CKAN API.

Queries the Argentina datos.gob.ar CKAN API for DNRPA (Dirección Nacional
de los Registros de la Propiedad Automotor) vehicle registration statistics.

Dataset: https://datos.gob.ar/dataset/justicia-estadistica-tramites-automotores
Free REST API, no auth required.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.dnrpa_estadisticas import DnrpaEstadistica, DnrpaEstadisticasResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CKAN_API_URL = "https://datos.gob.ar/api/3/action/package_show"
DATASET_ID = "justicia-estadistica-tramites-automotores"


@register
class DnrpaEstadisticasSource(BaseSource):
    """Query DNRPA vehicle registration statistics via datos.gob.ar CKAN API."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.dnrpa_estadisticas",
            display_name="DNRPA — Estadísticas de Trámites Automotores",
            description=(
                "Argentina DNRPA vehicle registration statistics: tramite counts "
                "by type, province, year, and month (datos.gob.ar CKAN API)"
            ),
            country="AR",
            url="https://datos.gob.ar/dataset/justicia-estadistica-tramites-automotores",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        year = input.extra.get("year", "").strip()
        month = input.extra.get("month", "").strip()
        search_term = " | ".join(filter(None, [year, month])) or "all"
        return self._fetch(year, month, search_term)

    def _fetch(self, year: str, month: str, search_term: str) -> DnrpaEstadisticasResult:
        try:
            logger.info(
                "Fetching DNRPA estadisticas: year=%s month=%s", year or "all", month or "all"
            )

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }

            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                # Step 1: Get dataset metadata to find CSV resource URL
                meta_resp = client.get(CKAN_API_URL, params={"id": DATASET_ID})
                meta_resp.raise_for_status()
                meta_data = meta_resp.json()

            if not meta_data.get("success"):
                raise SourceError(
                    "ar.dnrpa_estadisticas",
                    f"CKAN API error: {meta_data.get('error', 'unknown')}",
                )

            resources = meta_data.get("result", {}).get("resources", [])
            csv_url = _find_csv_resource(resources, year)

            if not csv_url:
                raise SourceError(
                    "ar.dnrpa_estadisticas",
                    "No CSV resource found in DNRPA dataset",
                )

            logger.info("Downloading DNRPA CSV: %s", csv_url)
            with httpx.Client(
                timeout=self._timeout, headers=headers, follow_redirects=True
            ) as client:
                csv_resp = client.get(csv_url)
                csv_resp.raise_for_status()
                csv_content = csv_resp.text

            return self._parse_csv(csv_content, year, month, search_term)

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "ar.dnrpa_estadisticas", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("ar.dnrpa_estadisticas", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("ar.dnrpa_estadisticas", f"Query failed: {e}") from e

    def _parse_csv(
        self, csv_content: str, year: str, month: str, search_term: str
    ) -> DnrpaEstadisticasResult:
        estadisticas: list[DnrpaEstadistica] = []

        reader = csv.DictReader(io.StringIO(csv_content))
        for row in reader:
            # Normalize keys (lowercase, strip)
            norm = {k.lower().strip(): (v or "").strip() for k, v in row.items()}

            row_year = _extract_field(norm, ["anio", "año", "year", "periodo_anio"])
            row_month = _extract_field(norm, ["mes", "month", "periodo_mes"])
            row_province = _extract_field(norm, ["provincia", "province", "distrito"])
            row_type = _extract_field(norm, ["tipo_tramite", "tramite", "tipo", "acto"])
            row_qty_raw = _extract_field(norm, ["cantidad", "quantity", "total", "valor"])

            # Apply year/month filters
            if year and row_year and row_year != year:
                continue
            if month and row_month and row_month.lstrip("0") != month.lstrip("0"):
                continue

            try:
                qty = int(float(row_qty_raw.replace(",", "") or "0"))
            except (ValueError, TypeError):
                qty = 0

            estadisticas.append(
                DnrpaEstadistica(
                    year=row_year,
                    month=row_month,
                    province=row_province,
                    tramite_type=row_type,
                    quantity=qty,
                )
            )

        return DnrpaEstadisticasResult(
            queried_at=datetime.now(),
            search_term=search_term,
            total_records=len(estadisticas),
            estadisticas=estadisticas,
        )


def _find_csv_resource(resources: list[dict], year: str) -> str:
    """Find the best CSV resource URL, optionally filtered by year."""
    csv_urls: list[tuple[str, str]] = []
    for res in resources:
        fmt = (res.get("format", "") or "").upper()
        url = res.get("url", "") or ""
        name = (res.get("name", "") or res.get("description", "") or "").lower()
        if fmt == "CSV" or url.lower().endswith(".csv"):
            csv_urls.append((url, name))

    if not csv_urls:
        return ""

    # If year filter provided, prefer a resource matching that year
    if year:
        for url, name in csv_urls:
            if year in name or year in url:
                return url

    # Return the last (most recent) CSV
    return csv_urls[-1][0]


def _extract_field(norm: dict[str, str], candidates: list[str]) -> str:
    """Extract first matching field from normalized row dict."""
    for key in candidates:
        if key in norm:
            return norm[key]
    return ""
