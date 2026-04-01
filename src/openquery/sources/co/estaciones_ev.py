"""Estaciones EV source — Colombian EV charging stations via Socrata API.

Queries Colombia's open data portal (datos.gov.co) for electric vehicle charging stations.
No browser or CAPTCHA required — direct HTTP API.

API: https://www.datos.gov.co/resource/qqm3-dw2u.json
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.estaciones_ev import EstacionEVResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.datos.gov.co/resource/qqm3-dw2u.json"


def _fix_coord(value: str) -> str:
    """Fix Colombian locale decimals: replace comma with dot for lat/lon."""
    if isinstance(value, str):
        return value.replace(",", ".")
    return str(value)


@register
class EstacionesEVSource(BaseSource):
    """Query Colombian EV charging stations from datos.gov.co."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.estaciones_ev",
            display_name="Estaciones EV — Electrolineras Colombia",
            description="Colombian EV charging stations from datos.gov.co (Socrata API)",
            country="CO",
            url=API_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query EV charging stations, optionally filtered by city."""
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("co.estaciones_ev", f"Unsupported input type: {input.document_type}")

        ciudad = input.extra.get("ciudad", "").strip()

        try:
            conditions = [
                "tipo_de_estacion='Estación de carga eléctrica EPM'"
            ]
            if ciudad:
                # Socrata upper() preserves accents, so use starts_with
                # to handle "Medellin" matching "Medellín"
                prefix = ciudad.strip()[:5].upper()
                conditions.append(
                    f"starts_with(upper(ciudad), '{prefix}')"
                )

            where_clause = " AND ".join(conditions)
            params: dict[str, str] = {"$where": where_clause, "$limit": "500"}

            logger.info("Querying EV stations: %s", where_clause)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            logger.info("Received %d EV station records", len(data))

            estaciones = []
            for row in data:
                estaciones.append({
                    "nombre": row.get("estaci_n", ""),
                    "direccion": row.get("direcci_n", ""),
                    "tipo": row.get("tipo", ""),
                    "horario": row.get("horario", ""),
                    "conector": row.get("est_ndar_cargador", ""),
                    "latitud": _fix_coord(row.get("latitud", "")),
                    "longitud": _fix_coord(row.get("longitud", "")),
                })

            return EstacionEVResult(
                ciudad=ciudad or "ALL",
                estaciones=estaciones,
                total=len(estaciones),
            )

        except SourceError:
            raise
        except httpx.HTTPStatusError as e:
            msg = f"API returned HTTP {e.response.status_code}"
            raise SourceError("co.estaciones_ev", msg) from e
        except httpx.RequestError as e:
            raise SourceError("co.estaciones_ev", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("co.estaciones_ev", f"Query failed: {e}") from e
