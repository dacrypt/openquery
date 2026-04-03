"""Ecuador SRI Establecimientos source — business establishment details.

Queries SRI for establishment details (branches, addresses) by RUC.
Free REST API, no auth, no CAPTCHA.

API: https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet/rest/Establecimiento/consultarPorNumeroRuc
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ec.sri_establecimientos import EcSriEstablecimientosResult, Establecimiento
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet/rest/Establecimiento/consultarPorNumeroRuc"


@register
class EcSriEstablecimientosSource(BaseSource):
    """Query Ecuador SRI establishment details by RUC."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ec.sri_establecimientos",
            display_name="SRI — Establecimientos por RUC",
            description="Ecuador business establishments: branches, addresses, status (SRI API)",
            country="EC",
            url=API_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        ruc = input.extra.get("ruc", "") or input.document_number
        if not ruc:
            raise SourceError("ec.sri_establecimientos", "RUC is required")
        return self._query(ruc.strip())

    def _query(self, ruc: str) -> EcSriEstablecimientosResult:
        try:
            logger.info("Querying SRI establecimientos: %s", ruc)
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params={"numeroRuc": ruc})
                resp.raise_for_status()
                data = resp.json()

            items = data if isinstance(data, list) else [data] if isinstance(data, dict) else []

            establecimientos = []
            for e in items:
                establecimientos.append(Establecimiento(
                    nombre_fantasia=e.get("nombreFantasiaComercial", "") or "",
                    tipo=e.get("tipoEstablecimiento", "") or "",
                    direccion=e.get("direccionCompleta", "") or "",
                    estado=e.get("estado", "") or "",
                    numero=e.get("numeroEstablecimiento", "") or "",
                ))

            return EcSriEstablecimientosResult(
                queried_at=datetime.now(),
                ruc=ruc,
                total=len(establecimientos),
                establecimientos=establecimientos,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("ec.sri_establecimientos", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("ec.sri_establecimientos", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("ec.sri_establecimientos", f"Query failed: {e}") from e
