"""SRI RUC source — Ecuador taxpayer registry via SRI API.

Queries Ecuador's SRI (Servicio de Rentas Internas) for taxpayer information
by RUC number. No browser required — direct HTTP API.

API: https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet/rest/ConsolidadoContribuyente/obtenerPorNumerosRuc
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ec.sri_ruc import SriRucResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet/rest/ConsolidadoContribuyente/obtenerPorNumerosRuc"


@register
class SriRucSource(BaseSource):
    """Query Ecuador taxpayer registry from SRI."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ec.sri_ruc",
            display_name="SRI — Registro Unico de Contribuyentes",
            description="Ecuador taxpayer registry (RUC) lookup from SRI",
            country="EC",
            url=API_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query taxpayer info by RUC number."""
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("ec.sri_ruc", f"Unsupported input type: {input.document_type}")

        ruc = input.extra.get("ruc", "").strip()
        token = input.extra.get("token", "").strip()

        if not ruc:
            raise SourceError("ec.sri_ruc", "Must provide extra['ruc'] (RUC number)")
        if not token:
            raise SourceError("ec.sri_ruc", "Must provide extra['token'] (authorization token)")

        try:
            headers = {
                "Authorization": token,
                "Content-Type": "application/json",
            }
            params = {"numeroRuc": ruc}

            logger.info("Querying SRI RUC: %s", ruc)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            logger.info("SRI RUC response received for %s", ruc)

            # The API may return a single object or a list
            record = data if isinstance(data, dict) else (data[0] if data else {})

            return SriRucResult(
                ruc=record.get("numeroRuc", ruc),
                razon_social=record.get("razonSocial", ""),
                nombre_comercial=record.get("nombreComercial", ""),
                estado=record.get("estadoContribuyente", record.get("estado", "")),
                actividad_economica=record.get("actividadEconomicaPrincipal", ""),
                direccion=record.get("direccionMatriz", record.get("direccion", "")),
                tipo_contribuyente=record.get("tipoContribuyente", ""),
                obligado_contabilidad=record.get("obligadoContabilidad", ""),
                fecha_inicio_actividades=record.get("fechaInicioActividades", ""),
            )

        except SourceError:
            raise
        except httpx.HTTPStatusError as e:
            msg = f"API returned HTTP {e.response.status_code}"
            raise SourceError("ec.sri_ruc", msg) from e
        except httpx.RequestError as e:
            raise SourceError("ec.sri_ruc", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("ec.sri_ruc", f"Query failed: {e}") from e
