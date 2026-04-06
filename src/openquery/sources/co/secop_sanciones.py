"""SECOP Sanciones source — Colombian contractor sanctions via Socrata API.

Queries Colombia's open data portal (datos.gov.co) for contractor
fines and sanctions from SECOP. No browser or CAPTCHA required.

API: https://www.datos.gov.co/resource/4n4q-k399.json
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.secop_sanciones import SecopSancion, SecopSancionesResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.datos.gov.co/resource/4n4q-k399.json"


@register
class SecopSancionesSource(BaseSource):
    """Query Colombian contractor sanctions from SECOP (datos.gov.co)."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.secop_sanciones",
            display_name="SECOP — Multas y Sanciones a Contratistas",
            description="Colombian contractor fines and sanctions from SECOP (datos.gov.co)",
            country="CO",
            url="https://www.datos.gov.co/Gastos-Gubernamentales/Multas-y-Sanciones/4n4q-k399",
            supported_inputs=[DocumentType.NIT, DocumentType.CEDULA, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        doc = input.document_number.strip()
        name = input.extra.get("name", "").strip()
        if not doc and not name:
            raise SourceError("co.secop_sanciones", "Provide a NIT/cedula or name (extra.name)")

        if doc:
            where = f"documento_contratista='{doc}'"
        else:
            prefix = name[:10].upper()
            where = f"starts_with(upper(nombre_contratista), '{prefix}')"

        return self._fetch(where, doc or name)

    def _fetch(self, where_clause: str, query_label: str) -> SecopSancionesResult:
        try:
            params = {"$where": where_clause, "$limit": "100"}
            logger.info("Querying SECOP sanciones: %s", where_clause)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            logger.info("Received %d sanction records", len(data))

            sanciones = []
            for row in data:
                sanciones.append(
                    SecopSancion(
                        proveedor=row.get("nombre_contratista", ""),
                        nit=row.get("documento_contratista", ""),
                        tipo_sancion=row.get("numero_de_resolucion", ""),
                        entidad=row.get("nombre_entidad", ""),
                        fecha_sancion=row.get("fecha_de_publicacion", ""),
                        valor=row.get("valor_sancion", ""),
                        estado=row.get("numero_de_contrato", ""),
                    )
                )

            return SecopSancionesResult(
                query=query_label,
                total=len(sanciones),
                sanciones=sanciones,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "co.secop_sanciones", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("co.secop_sanciones", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("co.secop_sanciones", f"Query failed: {e}") from e
