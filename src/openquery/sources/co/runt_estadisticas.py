"""RUNT fleet statistics source — Colombia vehicle fleet data via Socrata API.

Queries the datos.gov.co Socrata SODA API for RUNT fleet statistics
by brand, class, department, service type, and fuel type.
Free REST API, no auth required.

API: https://www.datos.gov.co/resource/u3vn-bdcy.json
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.runt_estadisticas import RuntEstadistica, RuntEstadisticasResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.datos.gov.co/resource/u3vn-bdcy.json"


@register
class RuntEstadisticasSource(BaseSource):
    """Query RUNT fleet statistics via datos.gov.co Socrata API."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.runt_estadisticas",
            display_name="RUNT — Estadísticas de Parque Automotor",
            description=(
                "Colombia RUNT fleet statistics: vehicle counts by brand, class, "
                "service type, fuel type, and department (datos.gov.co Socrata API)"
            ),
            country="CO",
            url="https://www.datos.gov.co/resource/u3vn-bdcy.json",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        marca = input.extra.get("marca", "").strip()
        clase = input.extra.get("clase", "").strip()
        departamento = input.extra.get("departamento", "").strip()
        search_term = " | ".join(filter(None, [marca, clase, departamento])) or "all"
        return self._fetch(marca, clase, departamento, search_term)

    def _fetch(
        self, marca: str, clase: str, departamento: str, search_term: str
    ) -> RuntEstadisticasResult:
        try:
            params: dict[str, str] = {"$limit": "1000"}

            # Build $where clause from provided filters
            conditions: list[str] = []
            if marca:
                safe = marca.replace("'", "''")
                conditions.append(f"upper(marca) = upper('{safe}')")
            if clase:
                safe = clase.replace("'", "''")
                conditions.append(f"upper(clase) = upper('{safe}')")
            if departamento:
                safe = departamento.replace("'", "''")
                conditions.append(f"upper(departamento) = upper('{safe}')")

            if conditions:
                params["$where"] = " AND ".join(conditions)

            logger.info(
                "Querying RUNT estadisticas: marca=%s clase=%s departamento=%s",
                marca,
                clase,
                departamento,
            )

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                records = resp.json()

            estadisticas: list[RuntEstadistica] = []
            total_vehiculos = 0

            for rec in records:
                try:
                    cantidad = int(rec.get("cantidad", 0) or 0)
                except (ValueError, TypeError):
                    cantidad = 0

                total_vehiculos += cantidad
                estadisticas.append(
                    RuntEstadistica(
                        marca=str(rec.get("marca", "") or ""),
                        clase=str(rec.get("clase", "") or ""),
                        servicio=str(rec.get("servicio", "") or ""),
                        combustible=str(rec.get("combustible", "") or ""),
                        departamento=str(rec.get("departamento", "") or ""),
                        cantidad=cantidad,
                    )
                )

            return RuntEstadisticasResult(
                queried_at=datetime.now(),
                search_term=search_term,
                total_records=len(estadisticas),
                total_vehiculos=total_vehiculos,
                estadisticas=estadisticas,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "co.runt_estadisticas", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("co.runt_estadisticas", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("co.runt_estadisticas", f"Query failed: {e}") from e
