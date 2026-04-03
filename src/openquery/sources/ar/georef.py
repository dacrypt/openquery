"""Argentina GeoRef source — address normalization and geocoding.

Queries Argentina's GeoRef API for address normalization and geocoding.
Free REST API, no auth, no CAPTCHA.

API: https://apis.datos.gob.ar/georef/api/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.georef import ArGeorefResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://apis.datos.gob.ar/georef/api/direcciones"


@register
class ArGeorefSource(BaseSource):
    """Query Argentine address normalization/geocoding via GeoRef API."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.georef",
            display_name="GeoRef — Normalización de Direcciones",
            description="Argentine address normalization and geocoding (datos.gob.ar GeoRef API)",
            country="AR",
            url="https://apis.datos.gob.ar/georef/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        direccion = input.extra.get("direccion", "") or input.document_number
        provincia = input.extra.get("provincia", "")
        if not direccion:
            raise SourceError("ar.georef", "Dirección is required (extra.direccion)")
        return self._query(direccion.strip(), provincia)

    def _query(self, direccion: str, provincia: str = "") -> ArGeorefResult:
        try:
            params: dict[str, str] = {"direccion": direccion, "max": "1"}
            if provincia:
                params["provincia"] = provincia

            logger.info("Querying GeoRef: %s", direccion)
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            dirs = data.get("direcciones", [])
            total = data.get("cantidad", 0)

            if not dirs:
                return ArGeorefResult(
                    queried_at=datetime.now(),
                    direccion=direccion,
                    total_resultados=0,
                )

            d = dirs[0]
            ubicacion = d.get("ubicacion", {})

            return ArGeorefResult(
                queried_at=datetime.now(),
                direccion=direccion,
                direccion_normalizada=d.get("nomenclatura", ""),
                provincia=ubicacion.get("provincia", {}).get("nombre", "") if isinstance(ubicacion.get("provincia"), dict) else "",
                departamento=ubicacion.get("departamento", {}).get("nombre", "") if isinstance(ubicacion.get("departamento"), dict) else "",
                localidad=ubicacion.get("localidad", {}).get("nombre", "") if isinstance(ubicacion.get("localidad"), dict) else "",
                latitud=ubicacion.get("lat", 0.0) or 0.0,
                longitud=ubicacion.get("lon", 0.0) or 0.0,
                total_resultados=total,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("ar.georef", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("ar.georef", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("ar.georef", f"Query failed: {e}") from e
