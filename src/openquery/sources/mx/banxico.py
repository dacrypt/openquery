"""Banxico source — Mexico central bank economic indicators via SIE REST API.

Queries Banco de México's SIE (Sistema de Información Económica) API for
time series data such as exchange rates, inflation, and interest rates.

API: https://www.banxico.org.mx/SieAPIRest/service/v1/series/{series_id}/datos/oportuno
No auth required for public series; optional token increases rate limits.
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.banxico import BanxicoDataPoint, BanxicoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

BANXICO_BASE_URL = "https://www.banxico.org.mx/SieAPIRest/service/v1/series"


@register
class BanxicoSource(BaseSource):
    """Query Banco de México's SIE API for economic time series data."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.banxico",
            display_name="Banxico SIE — Indicadores Económicos",
            description=(
                "Banco de México economic indicators: exchange rates, inflation, interest rates"
                " via SIE REST API (e.g. SF43718 for USD/MXN)"
            ),
            country="MX",
            url=BANXICO_BASE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        series_id = input.extra.get("series_id", "") or input.document_number
        if not series_id:
            raise SourceError(
                "mx.banxico",
                "Series ID required (pass via extra.series_id or document_number, e.g. SF43718)",
            )
        return self._query(series_id.strip().upper())

    def _query(self, series_id: str) -> BanxicoResult:
        # Fetch series metadata and latest data point
        metadata_url = f"{BANXICO_BASE_URL}/{series_id}/datos/oportuno"
        headers = {"Accept": "application/json"}

        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                resp = client.get(metadata_url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "mx.banxico", f"Banxico API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("mx.banxico", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("mx.banxico", f"Query failed: {e}") from e

        return self._parse_response(series_id, data)

    def _parse_response(self, series_id: str, data: dict) -> BanxicoResult:
        result = BanxicoResult(queried_at=datetime.now(), series_id=series_id)

        bmx_series = data.get("bmx", {}).get("series", [])
        if not bmx_series:
            result.details = {"raw": data}
            return result

        series = bmx_series[0]
        result.series_name = series.get("titulo", "")

        data_points: list[BanxicoDataPoint] = []
        for dp in series.get("datos", []):
            data_points.append(
                BanxicoDataPoint(
                    date=dp.get("fecha", ""),
                    value=dp.get("dato", ""),
                )
            )
        result.data_points = data_points
        result.details = {
            "idSerie": series.get("idSerie", ""),
            "titulo": series.get("titulo", ""),
        }
        return result
