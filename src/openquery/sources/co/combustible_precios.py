"""Combustible precios source — Colombian fuel prices by city.

Queries Colombia's open data portal (datos.gov.co) for fuel prices by city.
Uses Socrata API, no browser required.

API: https://www.datos.gov.co/resource/43yz-mf4a.json (SICOM fuel prices dataset)
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.combustible_precios import CoCombustiblePreciosResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

# SICOM fuel prices dataset on datos.gov.co
API_URL = "https://www.datos.gov.co/resource/43yz-mf4a.json"


@register
class CombustiblePreciosSource(BaseSource):
    """Query Colombian fuel prices by city from datos.gov.co."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.combustible_precios",
            display_name="Combustible Precios — Precios de Combustible por Ciudad",
            description="Colombian fuel prices by city (gasolina/diesel/acpm) from datos.gov.co SICOM dataset",  # noqa: E501
            country="CO",
            url=API_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        ciudad = input.extra.get("ciudad", "").strip()
        combustible = input.extra.get("combustible", "").strip().lower()

        if not ciudad and not combustible:
            raise SourceError(
                "co.combustible_precios",
                "Provide extra['ciudad'] and/or extra['combustible'] (gasolina/diesel/acpm)",
            )

        try:
            conditions = []
            if ciudad:
                ciudad_upper = ciudad.upper()
                conditions.append(f"upper(municipio)='{ciudad_upper}'")
            if combustible:
                conditions.append(f"lower(combustible)='{combustible}'")

            where_clause = " AND ".join(conditions)
            params: dict[str, str] = {"$limit": "200"}
            if where_clause:
                params["$where"] = where_clause

            logger.info("Querying Colombian fuel prices: ciudad=%s combustible=%s", ciudad, combustible)  # noqa: E501

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            records = []
            for row in data:
                records.append({
                    "municipio": row.get("municipio", ""),
                    "departamento": row.get("departamento", ""),
                    "combustible": row.get("combustible", ""),
                    "precio_galon": row.get("precio", row.get("precio_galon", "")),
                    "fecha": row.get("fecha", row.get("fecha_vigencia", "")),
                })

            first = records[0] if records else {}
            return CoCombustiblePreciosResult(
                ciudad=first.get("municipio", ciudad),
                combustible=first.get("combustible", combustible),
                precio_galon=first.get("precio_galon", ""),
                fecha=first.get("fecha", ""),
                details=f"{len(records)} registro(s) encontrado(s)",
                records=records,
            )

        except SourceError:
            raise
        except httpx.HTTPStatusError as e:
            raise SourceError("co.combustible_precios", f"API returned HTTP {e.response.status_code}") from e  # noqa: E501
        except httpx.RequestError as e:
            raise SourceError("co.combustible_precios", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("co.combustible_precios", f"Query failed: {e}") from e
