"""EPM EV charging stations source — Colombia public EV/CNG stations (Socrata).

Queries the Colombia open data portal (datos.gov.co) for EPM public
EV and CNG charging stations. Supports filtering by city and department.
Socrata SODA API, no authentication required.

API: https://www.datos.gov.co/resource/qqm3-dw2u.json
Docs: https://dev.socrata.com/docs/endpoints.html
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.estaciones_ev_epm import EpmStation, EstacionesEvEpmResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.datos.gov.co/resource/qqm3-dw2u.json"


@register
class EstacionesEvEpmSource(BaseSource):
    """Query EPM EV charging stations from Colombia open data portal."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.estaciones_ev_epm",
            display_name="EPM — Estaciones de Carga Eléctrica (Colombia)",
            description=(
                "EPM public EV and CNG charging stations in Colombia. "
                "Source: datos.gov.co Socrata dataset qqm3-dw2u."
            ),
            country="CO",
            url="https://www.datos.gov.co/resource/qqm3-dw2u.json",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        extra = input.extra or {}
        ciudad = extra.get("ciudad", "").strip()
        departamento = extra.get("departamento", "").strip()

        return self._fetch(ciudad, departamento)

    def _fetch(self, ciudad: str, departamento: str) -> EstacionesEvEpmResult:
        try:
            params: dict[str, str | int] = {"$limit": 1000}

            conditions = []
            if ciudad:
                conditions.append(f"upper(ciudad) = upper('{ciudad}')")
            if departamento:
                conditions.append(f"upper(departamento) = upper('{departamento}')")
            if conditions:
                params["$where"] = " AND ".join(conditions)

            search_parts = []
            if ciudad:
                search_parts.append(f"ciudad={ciudad}")
            if departamento:
                search_parts.append(f"departamento={departamento}")
            search_str = " ".join(search_parts) if search_parts else "all"

            logger.info("Querying EPM EV stations: %s", search_str)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            stations: list[EpmStation] = []
            for item in data:
                lat_raw = item.get("latitud", "") or item.get("latitude", "") or ""
                lon_raw = item.get("longitud", "") or item.get("longitude", "") or ""
                try:
                    lat = float(lat_raw) if lat_raw else 0.0
                except (ValueError, TypeError):
                    lat = 0.0
                try:
                    lon = float(lon_raw) if lon_raw else 0.0
                except (ValueError, TypeError):
                    lon = 0.0

                stations.append(
                    EpmStation(
                        nombre=str(item.get("nombre", "") or ""),
                        direccion=str(item.get("direccion", "") or ""),
                        ciudad=str(item.get("ciudad", "") or ""),
                        departamento=str(item.get("departamento", "") or ""),
                        tipo=str(item.get("tipo", "") or ""),
                        latitud=lat,
                        longitud=lon,
                    )
                )

            logger.info("EPM EV returned %d stations for: %s", len(stations), search_str)
            return EstacionesEvEpmResult(
                queried_at=datetime.now(),
                search_params=search_str,
                total_stations=len(stations),
                stations=stations,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "co.estaciones_ev_epm", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("co.estaciones_ev_epm", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("co.estaciones_ev_epm", f"Query failed: {e}") from e
