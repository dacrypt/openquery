"""SECOP Procesos source — Colombian procurement processes via Socrata API.

Queries Colombia's open data portal (datos.gov.co) for government
procurement processes from SECOP II. No browser or CAPTCHA required.

API: https://www.datos.gov.co/resource/p6dx-8zbt.json
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.secop_procesos import SecopProceso, SecopProcesosResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.datos.gov.co/resource/p6dx-8zbt.json"


@register
class SecopProcesosSource(BaseSource):
    """Query Colombian procurement processes from SECOP II (datos.gov.co)."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.secop_procesos",
            display_name="SECOP — Procesos de Contratación",
            description="Colombian government procurement processes from SECOP II (datos.gov.co)",
            country="CO",
            url="https://www.datos.gov.co/Gastos-Gubernamentales/SECOP-II-Procesos/p6dx-8zbt",
            supported_inputs=[DocumentType.NIT, DocumentType.CEDULA, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        doc = input.document_number.strip()
        name = input.extra.get("name", "").strip()
        if not doc and not name:
            raise SourceError("co.secop_procesos", "Provide NIT/cedula or name (extra.name)")

        if doc:
            where = f"nit_del_proveedor_adjudicado='{doc}' OR nit_entidad='{doc}'"
        else:
            prefix = name[:10].upper()
            where = f"starts_with(upper(nombre_del_proveedor_adjudicado), '{prefix}')"

        return self._fetch(where, doc or name)

    def _fetch(self, where_clause: str, query_label: str) -> SecopProcesosResult:
        try:
            params = {"$where": where_clause, "$limit": "50"}
            logger.info("Querying SECOP procesos: %s", where_clause)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            logger.info("Received %d SECOP process records", len(data))

            procesos = []
            for row in data:
                procesos.append(
                    SecopProceso(
                        entidad=row.get("nombre_de_la_entidad", row.get("entidad", "")),
                        nit_entidad=row.get("nit_entidad", ""),
                        proceso=row.get("id_del_proceso", row.get("referencia_del_proceso", "")),
                        estado=row.get("estado_del_proceso", ""),
                        tipo_proceso=row.get("tipo_de_proceso", ""),
                        valor_proceso=row.get(
                            "precio_base", row.get("valor_total_adjudicacion", "")
                        ),
                        fecha_publicacion=row.get("fecha_de_publicacion_del_proceso", ""),
                        url_proceso=row.get("url_del_proceso", ""),
                    )
                )

            return SecopProcesosResult(
                query=query_label,
                total=len(procesos),
                procesos=procesos,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "co.secop_procesos", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("co.secop_procesos", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("co.secop_procesos", f"Query failed: {e}") from e
