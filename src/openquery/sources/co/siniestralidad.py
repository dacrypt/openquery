"""Siniestralidad source — Colombian road crash hotspots via Socrata API.

Queries Colombia's open data portal (datos.gov.co) for road crash data.
No browser or CAPTCHA required — direct HTTP API.

API: https://www.datos.gov.co/resource/rs3u-8r4q.json
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.siniestralidad import SiniestralidadResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.datos.gov.co/resource/rs3u-8r4q.json"


@register
class SiniestralidadSource(BaseSource):
    """Query Colombian road crash hotspot data from datos.gov.co."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.siniestralidad",
            display_name="Siniestralidad — Puntos Críticos Viales",
            description="Colombian road crash hotspots from datos.gov.co (Socrata API)",
            country="CO",
            url=API_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query road crash hotspots by department or municipality."""
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("co.siniestralidad", f"Unsupported input type: {input.document_type}")

        departamento = input.extra.get("departamento", "").strip().upper()
        municipio = input.extra.get("municipio", "").strip().upper()

        if not departamento and not municipio:
            raise SourceError(
                "co.siniestralidad",
                "Must provide extra['departamento'] or extra['municipio']",
            )

        try:
            conditions = []
            if departamento:
                conditions.append(f"departamento='{departamento}'")
            if municipio:
                conditions.append(f"municipio='{municipio}'")

            where_clause = " AND ".join(conditions)
            params: dict[str, str] = {"$where": where_clause, "$limit": "500"}

            logger.info("Querying crash hotspots: %s", where_clause)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            logger.info("Received %d crash hotspot records", len(data))

            sectores = []
            total_fallecidos = 0
            for row in data:
                fallecidos = int(row.get("fallecidos", 0) or 0)
                total_fallecidos += fallecidos
                sectores.append({
                    "tramo": row.get("tramo", ""),
                    "fallecidos": fallecidos,
                    "latitud": row.get("latitud", ""),
                    "longitud": row.get("longitud", ""),
                    "pr": row.get("pr", ""),
                })

            return SiniestralidadResult(
                departamento=departamento or (data[0].get("departamento", "") if data else ""),
                municipio=municipio or (data[0].get("municipio", "") if data else ""),
                sectores=sectores,
                total_sectores=len(sectores),
                total_fallecidos=total_fallecidos,
            )

        except SourceError:
            raise
        except httpx.HTTPStatusError as e:
            msg = f"API returned HTTP {e.response.status_code}"
            raise SourceError("co.siniestralidad", msg) from e
        except httpx.RequestError as e:
            raise SourceError("co.siniestralidad", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("co.siniestralidad", f"Query failed: {e}") from e
