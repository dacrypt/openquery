"""RNT Turismo source — Colombian national tourism registry via Socrata API.

Queries Colombia's open data portal (datos.gov.co) for tourism registry entries.
No browser or CAPTCHA required — direct HTTP API.

API: https://www.datos.gov.co/resource/2z2j-kxnj.json
Page: https://www.datos.gov.co/Comercio-Industria-y-Turismo/Registro-Nacional-de-Turismo-RNT-/2z2j-kxnj
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.rnt_turismo import RntTurismoEntry, RntTurismoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.datos.gov.co/resource/thwd-ivmp.json"
PAGE_URL = "https://www.datos.gov.co/Comercio-Industria-y-Turismo/Registro-Nacional-de-Turismo-RNT-/thwd-ivmp"


@register
class RntTurismoSource(BaseSource):
    """Query Colombian national tourism registry from datos.gov.co."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.rnt_turismo",
            display_name="RNT \u2014 Registro Nacional de Turismo",
            description="Colombian national tourism registry from datos.gov.co",
            country="CO",
            url=PAGE_URL,
            supported_inputs=[DocumentType.NIT, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query tourism registry by NIT or business name."""
        if input.document_type == DocumentType.NIT:
            return self._query_by_nit(input.document_number)
        elif input.document_type == DocumentType.CUSTOM:
            name = input.extra.get("name", "").strip()
            if not name:
                raise SourceError(
                    "co.rnt_turismo",
                    "Must provide extra['name'] when using CUSTOM document type",
                )
            return self._query_by_name(name)
        else:
            raise SourceError(
                "co.rnt_turismo",
                f"Unsupported document type: {input.document_type}. Use NIT or CUSTOM.",
            )

    def _query_by_nit(self, nit: str) -> RntTurismoResult:
        where_clause = f"upper(nit)='{nit.strip().upper()}'"
        return self._fetch(where_clause, query_label=nit)

    def _query_by_name(self, name: str) -> RntTurismoResult:
        prefix = name[:5].upper()
        where_clause = f"starts_with(upper(razon_social), '{prefix}')"
        return self._fetch(where_clause, query_label=name)

    def _fetch(self, where_clause: str, query_label: str) -> RntTurismoResult:
        try:
            params: dict[str, str] = {"$where": where_clause, "$limit": "500"}

            logger.info("Querying RNT turismo: %s", where_clause)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            logger.info("Received %d RNT records", len(data))

            registros = []
            for row in data:
                registros.append(
                    RntTurismoEntry(
                        rnt=row.get("rnt", row.get("numero_rnt", "")),
                        razon_social=row.get("razon_social", row.get("nombre_del_establecimiento", "")),
                        categoria=row.get("categoria", row.get("categor_a", "")),
                        subcategoria=row.get("subcategoria", row.get("subcategor_a", "")),
                        municipio=row.get("municipio", ""),
                        departamento=row.get("departamento", ""),
                        estado=row.get("estado", row.get("estado_del_registro", "")),
                        fecha_registro=row.get("fecha_registro", row.get("fecha_del_registro", "")),
                    )
                )

            return RntTurismoResult(
                query=query_label,
                total=len(registros),
                registros=registros,
            )

        except SourceError:
            raise
        except httpx.HTTPStatusError as e:
            msg = f"API returned HTTP {e.response.status_code}"
            raise SourceError("co.rnt_turismo", msg) from e
        except httpx.RequestError as e:
            raise SourceError("co.rnt_turismo", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("co.rnt_turismo", f"Query failed: {e}") from e
