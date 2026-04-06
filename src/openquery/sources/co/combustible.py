"""Combustible source — Colombian fuel prices via Socrata API.

Queries Colombia's open data portal (datos.gov.co) for gas station prices.
No browser or CAPTCHA required — direct HTTP API.

API: https://www.datos.gov.co/resource/gjy9-tpph.json
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.combustible import CombustibleResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.datos.gov.co/resource/gjy9-tpph.json"


@register
class CombustibleSource(BaseSource):
    """Query Colombian fuel prices from datos.gov.co."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.combustible",
            display_name="Combustible — Precios de Combustible",
            description="Colombian fuel prices by municipality from datos.gov.co (Socrata API)",
            country="CO",
            url=API_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query fuel prices by municipality or department."""
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("co.combustible", f"Unsupported input type: {input.document_type}")

        municipio = input.extra.get("municipio", "").strip().upper()
        departamento = input.extra.get("departamento", "").strip().upper()

        if not municipio and not departamento:
            raise SourceError(
                "co.combustible",
                "Must provide extra['municipio'] or extra['departamento']",
            )

        try:
            conditions = []
            if municipio:
                prefix = municipio[:5]
                conditions.append(f"starts_with(upper(municipio), '{prefix}')")
            if departamento:
                prefix_dep = departamento[:5]
                conditions.append(f"starts_with(upper(departamento), '{prefix_dep}')")

            where_clause = " AND ".join(conditions)
            params: dict[str, str] = {"$where": where_clause, "$limit": "500"}

            logger.info("Querying fuel prices: %s", where_clause)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            logger.info("Received %d fuel station records", len(data))

            estaciones = []
            for row in data:
                estaciones.append(
                    {
                        "nombre": row.get("nombre_comercial", ""),
                        "bandera": row.get("bandera", ""),
                        "direccion": row.get("direccion", ""),
                        "producto": row.get("producto", ""),
                        "precio": row.get("precio", ""),
                    }
                )

            return CombustibleResult(
                departamento=departamento or (data[0].get("departamento", "") if data else ""),
                municipio=municipio or (data[0].get("municipio", "") if data else ""),
                estaciones=estaciones,
                total_estaciones=len(estaciones),
            )

        except SourceError:
            raise
        except httpx.HTTPStatusError as e:
            msg = f"API returned HTTP {e.response.status_code}"
            raise SourceError("co.combustible", msg) from e
        except httpx.RequestError as e:
            raise SourceError("co.combustible", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("co.combustible", f"Query failed: {e}") from e
