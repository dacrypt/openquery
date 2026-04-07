"""Peajes tarifas source — Colombian toll booth tariffs.

Queries Colombia's open data portal (datos.gov.co) for toll tariffs by vehicle category.
Uses Socrata API, no browser required.

API: https://www.datos.gov.co/resource/dqv3-yfxh.json (INVIAS toll tariffs dataset)
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.peajes_tarifas import CoPeajesTarifasResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

# INVIAS toll tariffs dataset on datos.gov.co
API_URL = "https://www.datos.gov.co/resource/dqv3-yfxh.json"


@register
class PeajesTarifasSource(BaseSource):
    """Query Colombian toll tariffs by peaje and vehicle category."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.peajes_tarifas",
            display_name="Peajes INVIAS — Tarifas por Categoría",
            description="Colombian toll booth tariffs by vehicle category from datos.gov.co INVIAS dataset",  # noqa: E501
            country="CO",
            url=API_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        peaje = input.extra.get("peaje", "").strip()
        categoria = input.extra.get("categoria", "").strip()

        if not peaje and not categoria:
            raise SourceError(
                "co.peajes_tarifas",
                "Provide extra['peaje'] (toll name) and/or extra['categoria'] (vehicle category)",
            )

        try:
            conditions = []
            if peaje:
                peaje_upper = peaje.upper()
                conditions.append(f"upper(peaje) like '%{peaje_upper}%'")
            if categoria:
                categoria_upper = categoria.upper()
                conditions.append(f"upper(categoria) like '%{categoria_upper}%'")

            where_clause = " AND ".join(conditions)
            params: dict[str, str] = {"$limit": "200"}
            if where_clause:
                params["$where"] = where_clause

            logger.info("Querying Colombian toll tariffs: peaje=%s categoria=%s", peaje, categoria)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            records = []
            for row in data:
                records.append({
                    "peaje": row.get("peaje", row.get("nombre_peaje", "")),
                    "categoria": row.get("categoria", row.get("categoria_vehiculo", "")),
                    "tarifa": row.get("tarifa", row.get("valor_tarifa", "")),
                    "ruta": row.get("ruta", row.get("corredor", "")),
                    "departamento": row.get("departamento", ""),
                })

            first = records[0] if records else {}
            return CoPeajesTarifasResult(
                peaje=first.get("peaje", peaje),
                categoria=first.get("categoria", categoria),
                tarifa=first.get("tarifa", ""),
                ruta=first.get("ruta", ""),
                details=f"{len(records)} tarifa(s) encontrada(s)",
                records=records,
            )

        except SourceError:
            raise
        except httpx.HTTPStatusError as e:
            raise SourceError("co.peajes_tarifas", f"API returned HTTP {e.response.status_code}") from e  # noqa: E501
        except httpx.RequestError as e:
            raise SourceError("co.peajes_tarifas", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("co.peajes_tarifas", f"Query failed: {e}") from e
