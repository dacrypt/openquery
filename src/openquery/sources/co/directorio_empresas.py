"""Directorio de Empresas source — Colombian business directory.

Queries Colombia's open data portal (datos.gov.co) for the business
directory (Directorio de Empresas Activas).

Flow:
1. Query Socrata API with NIT or company name filter
2. Parse JSON response

API: https://www.datos.gov.co/resource/6q7c-bkcg.json
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.directorio_empresas import DirectorioEmpresasResult, EmpresaDirectorio
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.datos.gov.co/resource/6q7c-bkcg.json"


@register
class DirectorioEmpresasSource(BaseSource):
    """Query Colombian business directory from datos.gov.co."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.directorio_empresas",
            display_name="Directorio Empresas — datos.gov.co",
            description="Colombian business directory from open data portal (datos.gov.co)",
            country="CO",
            url=API_URL,
            supported_inputs=[DocumentType.NIT, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.document_number.strip()
        name = input.extra.get("name", "").strip()

        if not search_term and not name:
            raise SourceError(
                "co.directorio_empresas", "Provide a NIT or company name (extra.name)"
            )

        query_term = search_term if search_term else name
        tipo = "nit" if input.document_type == DocumentType.NIT else "nombre"
        return self._query(query_term, tipo)

    def _query(self, query: str, tipo: str) -> DirectorioEmpresasResult:
        from datetime import datetime

        try:
            if tipo == "nit":
                where_clause = f"nit='{query}'"
            else:
                prefix = query.upper()[:10]
                where_clause = f"starts_with(upper(raz_n_social), '{prefix}')"

            params: dict[str, str] = {"$where": where_clause, "$limit": "50"}

            logger.info("Querying business directory: %s", where_clause)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            logger.info("Received %d business records", len(data))

            empresas = []
            for row in data:
                empresas.append(
                    EmpresaDirectorio(
                        razon_social=row.get("raz_n_social", row.get("razon_social", "")),
                        nit=row.get("nit", ""),
                        actividad_economica=row.get(
                            "actividad_econ_mica", row.get("actividad_economica", "")
                        ),
                        ciiu=row.get("ciiu", row.get("c_digo_ciiu", "")),
                        direccion=row.get("direcci_n", row.get("direccion", "")),
                        municipio=row.get("municipio", ""),
                        departamento=row.get("departamento", ""),
                        telefono=row.get("tel_fono", row.get("telefono", "")),
                        estado=row.get("estado", row.get("estado_matr_cula", "")),
                    )
                )

            if not empresas:
                mensaje = "No se encontraron empresas"
            else:
                mensaje = f"Se encontraron {len(empresas)} empresa(s)"

            return DirectorioEmpresasResult(
                queried_at=datetime.now(),
                query=query,
                tipo_busqueda=tipo,
                empresas=empresas,
                total_empresas=len(empresas),
                mensaje=mensaje,
            )

        except SourceError:
            raise
        except httpx.HTTPStatusError as e:
            msg = f"API returned HTTP {e.response.status_code}"
            raise SourceError("co.directorio_empresas", msg) from e
        except httpx.RequestError as e:
            raise SourceError("co.directorio_empresas", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("co.directorio_empresas", f"Query failed: {e}") from e
