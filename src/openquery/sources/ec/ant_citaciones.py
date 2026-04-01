"""ANT Citaciones source — Ecuador traffic citations via ANT API.

Queries Ecuador's ANT (Agencia Nacional de Transito) for traffic citations
by cedula, plate, or custom identifier. No browser required — direct HTTP API.

API: https://consultaweb.ant.gob.ec/PortalWEB/paginas/clientes/clp_json_consulta_persona.jsp
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ec.ant_citaciones import AntCitacionesResult, Citacion
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://consultaweb.ant.gob.ec/PortalWEB/paginas/clientes/clp_json_consulta_persona.jsp"


@register
class AntCitacionesSource(BaseSource):
    """Query Ecuador traffic citations from ANT."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ec.ant_citaciones",
            display_name="ANT — Citaciones de Transito",
            description="Ecuador traffic citations and license points from ANT",
            country="EC",
            url=API_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.PLATE, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query traffic citations by cedula, plate, or custom identifier."""
        if input.document_type not in (DocumentType.CEDULA, DocumentType.PLATE, DocumentType.CUSTOM):
            raise SourceError("ec.ant_citaciones", f"Unsupported input type: {input.document_type}")

        documento = input.document_number.strip()
        if not documento:
            raise SourceError("ec.ant_citaciones", "Document number is required")

        try:
            params = {"identificacion": documento}

            logger.info("Querying ANT citaciones: %s", documento)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            logger.info("ANT citaciones response received for %s", documento)

            citaciones_raw = data.get("citaciones", data.get("infracciones", []))
            if isinstance(citaciones_raw, list):
                citaciones = [
                    Citacion(
                        numero=c.get("numero", c.get("numeroCitacion", "")),
                        fecha=c.get("fecha", c.get("fechaCitacion", "")),
                        tipo=c.get("tipo", c.get("tipoInfraccion", "")),
                        monto=str(c.get("monto", c.get("valor", ""))),
                        estado=c.get("estado", c.get("estadoCitacion", "")),
                        puntos=str(c.get("puntos", c.get("puntosReduccion", ""))),
                    )
                    for c in citaciones_raw
                ]
            else:
                citaciones = []

            puntos = str(data.get("puntosLicencia", data.get("puntos", "")))

            return AntCitacionesResult(
                documento=documento,
                citaciones=citaciones,
                total_citaciones=len(citaciones),
                puntos_licencia=puntos,
            )

        except SourceError:
            raise
        except httpx.HTTPStatusError as e:
            msg = f"API returned HTTP {e.response.status_code}"
            raise SourceError("ec.ant_citaciones", msg) from e
        except httpx.RequestError as e:
            raise SourceError("ec.ant_citaciones", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("ec.ant_citaciones", f"Query failed: {e}") from e
