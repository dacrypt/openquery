"""SECOP source — Colombian public procurement data via Socrata API.

Queries Colombia's open data portal (datos.gov.co) for public contracts
from SECOP II (Sistema Electronico de Contratacion Publica).
No browser or CAPTCHA required — direct HTTP API.

API: https://www.datos.gov.co/resource/jbjy-vk9h.json
Page: https://www.datos.gov.co/Gastos-Gubernamentales/SECOP-II-Contratos/jbjy-vk9h
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.secop import SecopContrato, SecopResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.datos.gov.co/resource/jbjy-vk9h.json"
PAGE_URL = "https://www.datos.gov.co/Gastos-Gubernamentales/SECOP-II-Contratos/jbjy-vk9h"


@register
class SecopSource(BaseSource):
    """Query Colombian public procurement data from SECOP II."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.secop",
            display_name="SECOP \u2014 Contrataci\u00f3n P\u00fablica",
            description="Colombian public procurement data from SECOP (datos.gov.co)",
            country="CO",
            url=PAGE_URL,
            supported_inputs=[DocumentType.NIT, DocumentType.CEDULA, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query SECOP contracts by NIT, cedula, or custom search."""
        if input.document_type == DocumentType.NIT:
            return self._query_by_documento(input.document_number)
        elif input.document_type == DocumentType.CEDULA:
            return self._query_by_documento(input.document_number)
        elif input.document_type == DocumentType.CUSTOM:
            nombre = input.extra.get("nombre", "").strip()
            if not nombre:
                raise SourceError(
                    "co.secop",
                    "CUSTOM input requires extra['nombre'] with provider name",
                )
            return self._query_by_nombre(nombre)
        else:
            raise SourceError("co.secop", f"Unsupported input type: {input.document_type}")

    def _query_by_documento(self, documento: str) -> SecopResult:
        """Query contracts by provider NIT or cedula."""
        where = f"documento_proveedor='{documento}'"
        logger.info("Querying SECOP by documento_proveedor=%s", documento)
        data = self._fetch(where)
        return self._build_result(data, documento=documento)

    def _query_by_nombre(self, nombre: str) -> SecopResult:
        """Query contracts by provider name (full-text search)."""
        logger.info("Querying SECOP by nombre=%s", nombre)
        data = self._fetch_q(nombre)
        return self._build_result(data, nombre_proveedor=nombre)

    def _fetch(self, where: str) -> list[dict]:
        """Execute Socrata API query with $where filter."""
        params: dict[str, str] = {
            "$where": where,
            "$limit": "200",
            "$order": "fecha_de_firma DESC",
        }
        return self._do_fetch(params)

    def _fetch_q(self, q: str) -> list[dict]:
        """Execute Socrata API full-text search with $q parameter."""
        params: dict[str, str] = {
            "$q": q,
            "$limit": "200",
            "$order": "fecha_de_firma DESC",
        }
        return self._do_fetch(params)

    def _do_fetch(self, params: dict[str, str]) -> list[dict]:
        """Execute Socrata API query."""
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            logger.info("Received %d SECOP contract records", len(data))
            return data

        except httpx.HTTPStatusError as e:
            raise SourceError("co.secop", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("co.secop", f"Request failed: {e}") from e

    def _build_result(
        self,
        data: list[dict],
        documento: str = "",
        nombre_proveedor: str = "",
    ) -> SecopResult:
        """Parse raw API rows into SecopResult."""
        contratos = []
        for row in data:
            contratos.append(
                SecopContrato(
                    proceso=row.get("proceso_de_compra", row.get("numero_del_contrato", "")),
                    entidad=row.get("nombre_entidad", row.get("entidad", "")),
                    objeto=row.get("descripcion_del_proceso", row.get("objeto_del_contrato", "")),
                    tipo_contrato=row.get("tipo_de_contrato", ""),
                    valor=row.get("valor_del_contrato", row.get("valor_total", "")),
                    estado=row.get("estado_contrato", row.get("estado_del_contrato", "")),
                    fecha_firma=row.get("fecha_de_firma", ""),
                )
            )

        # Extract provider name from first result if not given
        if not nombre_proveedor and data:
            nombre_proveedor = data[0].get("nombre_del_proveedor", "")

        if not documento and data:
            documento = data[0].get("documento_proveedor", "")

        return SecopResult(
            documento=documento,
            nombre_proveedor=nombre_proveedor,
            total_contratos=len(contratos),
            contratos=contratos,
        )
