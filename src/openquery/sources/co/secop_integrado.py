"""SECOP Integrado source — Colombian unified procurement via Socrata API.

Queries the unified SECOP I + SECOP II procurement dataset.
No browser or CAPTCHA required.

API: https://www.datos.gov.co/resource/rpmr-utcd.json
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.secop_integrado import SecopContrato, SecopIntegradoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.datos.gov.co/resource/rpmr-utcd.json"


@register
class SecopIntegradoSource(BaseSource):
    """Query Colombian unified procurement (SECOP I + II) from datos.gov.co."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.secop_integrado",
            display_name="SECOP Integrado — Contratación Unificada",
            description="Colombian unified procurement contracts SECOP I + II (datos.gov.co)",
            country="CO",
            url="https://www.datos.gov.co/Gastos-Gubernamentales/SECOP-Integrado/rpmr-utcd",
            supported_inputs=[DocumentType.NIT, DocumentType.CEDULA, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        doc = input.document_number.strip()
        name = input.extra.get("name", "").strip()
        if not doc and not name:
            raise SourceError("co.secop_integrado", "Provide NIT/cedula or name (extra.name)")

        if doc:
            where = f"documento_proveedor='{doc}' OR nit_de_la_entidad='{doc}'"
        else:
            prefix = name[:10].upper()
            where = f"starts_with(upper(nombre_del_proveedor), '{prefix}')"

        return self._fetch(where, doc or name)

    def _fetch(self, where_clause: str, query_label: str) -> SecopIntegradoResult:
        try:
            params = {"$where": where_clause, "$limit": "50"}
            logger.info("Querying SECOP integrado: %s", where_clause)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            logger.info("Received %d SECOP integrado records", len(data))

            contratos = []
            for row in data:
                contratos.append(
                    SecopContrato(
                        entidad=row.get("nombre_de_la_entidad", ""),
                        nit_entidad=row.get("nit_de_la_entidad", ""),
                        proveedor=row.get(
                            "nombre_del_proveedor", row.get("proveedor_adjudicado", "")
                        ),
                        documento_proveedor=row.get("documento_proveedor", ""),
                        estado=row.get("estado_del_proceso", ""),
                        modalidad=row.get("modalidad_de_contrataci_n", ""),
                        objeto=row.get("objeto_a_contratar", "")[:200],
                        valor=row.get("valor_total_de_adjudicacion", row.get("valor_contrato", "")),
                        departamento=row.get("departamento_entidad", ""),
                        municipio=row.get("municipio_entidad", ""),
                    )
                )

            return SecopIntegradoResult(
                query=query_label,
                total=len(contratos),
                contratos=contratos,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "co.secop_integrado", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("co.secop_integrado", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("co.secop_integrado", f"Query failed: {e}") from e
