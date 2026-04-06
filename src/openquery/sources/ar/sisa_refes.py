"""Argentina SISA REFES source — health facility registry.

Queries SISA's WS001 endpoint for health establishment details by name, province, or code.

API: https://sisa.msal.gov.ar/sisa/#sisa/api/ws001
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.sisa_refes import SisaRefesResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SISA_URL = "https://sisa.msal.gov.ar/sisa/"
SISA_API_URL = "https://sisa.msal.gov.ar/sisa/services/rest/establecimiento/get"


@register
class SisaRefesSource(BaseSource):
    """Query Argentine SISA health facility registry by name, province, or code."""

    def __init__(self, timeout: float = 20.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.sisa_refes",
            display_name="SISA REFES — Registro Federal de Establecimientos de Salud",
            description=(
                "Argentine health facility registry: name, type, CUIT, address, province, services"
            ),
            country="AR",
            url=SISA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("facility_name", "")
            or input.extra.get("province", "")
            or input.extra.get("code", "")
            or input.document_number
        )
        if not search_term:
            raise SourceError(
                "ar.sisa_refes",
                "Search term is required (extra.facility_name, extra.province, or extra.code)",
            )
        return self._query(
            search_term=search_term,
            province=input.extra.get("province", ""),
            code=input.extra.get("code", ""),
        )

    def _query(self, search_term: str, province: str = "", code: str = "") -> SisaRefesResult:
        try:
            params: dict[str, str] = {}
            if code:
                params["cuie"] = code
            elif province:
                params["provincia"] = province
                params["nombre"] = search_term
            else:
                params["nombre"] = search_term

            logger.info("Querying SISA REFES: %s", search_term)
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(SISA_API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            return self._parse_response(search_term, data)

        except httpx.HTTPStatusError as e:
            raise SourceError("ar.sisa_refes", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("ar.sisa_refes", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("ar.sisa_refes", f"Query failed: {e}") from e

    def _parse_response(self, search_term: str, data: dict) -> SisaRefesResult:
        from datetime import datetime

        result = SisaRefesResult(queried_at=datetime.now(), search_term=search_term)

        # WS001 may return a single record or a list under "establecimientos"
        record: dict = {}
        if isinstance(data, dict):
            establecimientos = data.get("establecimientos", data.get("resultado", []))
            if isinstance(establecimientos, list) and establecimientos:
                record = establecimientos[0]
            elif isinstance(data, dict) and data.get("nombre"):
                record = data

        if not record:
            return result

        result.facility_name = record.get("nombre", "")
        result.facility_type = record.get("tipoEstablecimiento", record.get("tipo", ""))
        result.cuit = str(record.get("cuit", ""))
        prov = record.get("provincia")
        result.province = prov.get("nombre", "") if isinstance(prov, dict) else str(prov or "")
        result.sector = record.get("sector", "")

        # Build address from components
        domicilio = record.get("domicilio", {})
        if isinstance(domicilio, dict):
            parts = [
                domicilio.get("calle", ""),
                domicilio.get("numero", ""),
                domicilio.get("localidad", ""),
            ]
            result.address = " ".join(p for p in parts if p)
        elif isinstance(domicilio, str):
            result.address = domicilio

        # Services list
        servicios = record.get("servicios", [])
        if isinstance(servicios, list):
            result.services = [
                s.get("nombre", str(s)) if isinstance(s, dict) else str(s) for s in servicios
            ]

        # Flatten remaining keys into details
        skip = {
            "nombre",
            "tipoEstablecimiento",
            "tipo",
            "cuit",
            "provincia",
            "sector",
            "domicilio",
            "servicios",
        }
        result.details = {
            k: str(v)
            for k, v in record.items()
            if k not in skip and v is not None and not isinstance(v, (dict, list))
        }

        return result
