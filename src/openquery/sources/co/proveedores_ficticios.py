"""Proveedores Ficticios source — DIAN fictitious providers list.

Queries the DIAN's list of fictitious or nonexistent providers for
compliance screening purposes.

Uses datos.gov.co Socrata API.
No browser or CAPTCHA required — direct HTTP.

API: https://www.datos.gov.co/resource/9kgd-yzwq.json
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.proveedores_ficticios import (
    ProveedoresFicticiosResult,
    ProveedorFicticioEntry,
)
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.datos.gov.co/resource/9kgd-yzwq.json"
PAGE_URL = "https://www.datos.gov.co/Hacienda/Proveedores-Ficticios/9kgd-yzwq"


@register
class ProveedoresFicticiosSource(BaseSource):
    """Screen NIT/names against DIAN fictitious providers list."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.proveedores_ficticios",
            display_name="DIAN — Proveedores Ficticios",
            description="DIAN fictitious/nonexistent providers list for compliance screening",
            country="CO",
            url=PAGE_URL,
            supported_inputs=[DocumentType.NIT, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        nit = input.document_number.strip()
        name = input.extra.get("name", "").strip()

        if not nit and not name:
            raise SourceError("co.proveedores_ficticios", "Provide a NIT or name (extra.name)")

        return self._search(nit, name)

    def _search(self, nit: str, nombre: str = "") -> ProveedoresFicticiosResult:
        try:
            params: dict[str, str] = {"$limit": "50"}

            if nit:
                params["$where"] = f"nit='{nit}'"
                logger.info("Searching fictitious providers by NIT: %s", nit)
            elif nombre:
                search_upper = nombre.upper()
                params["$where"] = f"upper(razon_social) like '%25{search_upper}%25'"
                logger.info("Searching fictitious providers by name: %s", nombre)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            registros = []
            for entry in data:
                registros.append(
                    ProveedorFicticioEntry(
                        nit=entry.get("nit", ""),
                        razon_social=entry.get("razon_social", entry.get("nombre", "")),
                        resolucion=entry.get("resolucion", entry.get("numero_resolucion", "")),
                        fecha_resolucion=entry.get("fecha_resolucion", entry.get("fecha", "")),
                        estado=entry.get("estado", ""),
                    )
                )

            return ProveedoresFicticiosResult(
                queried_at=datetime.now(),
                query=nit or nombre,
                es_proveedor_ficticio=len(registros) > 0,
                match_count=len(registros),
                registros=registros,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "co.proveedores_ficticios", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("co.proveedores_ficticios", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("co.proveedores_ficticios", f"Search failed: {e}") from e
