"""Vehiculos source — Colombian national vehicle fleet data.

Queries Colombia's open data portal (datos.gov.co) for vehicle
registration records. No browser or CAPTCHA needed.

API: https://www.datos.gov.co/resource/g7i9-xkxz.json
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.vehiculos import VehiculosResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.datos.gov.co/resource/g7i9-xkxz.json"


@register
class VehiculosSource(BaseSource):
    """Query Colombian national vehicle fleet data from datos.gov.co."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.vehiculos",
            display_name="Datos.gov.co — Parque Automotor Nacional",
            description="Colombian national vehicle fleet data from open data portal",
            country="CO",
            url=API_URL,
            supported_inputs=[DocumentType.PLATE, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query vehicle data by plate or brand.

        For PLATE: queries by exact plate number.
        For CUSTOM: expects extra["marca"] for brand search.
        """
        if input.document_type == DocumentType.PLATE:
            placa = input.document_number.upper().strip()
            if not placa:
                raise SourceError("co.vehiculos", "Plate number is required")
            return self._query_by_plate(placa)

        elif input.document_type == DocumentType.CUSTOM:
            marca = input.extra.get("marca", "").upper().strip()
            if not marca:
                raise SourceError("co.vehiculos", "extra['marca'] is required")
            return self._query_by_brand(marca)

        else:
            raise SourceError(
                "co.vehiculos",
                f"Unsupported input type: {input.document_type}. "
                "Use PLATE or CUSTOM with extra['marca']",
            )

    def _query_by_plate(self, placa: str) -> VehiculosResult:
        """Query by exact plate number."""
        placa = placa.upper().strip()

        params = {
            "$where": f"placa='{placa}'",
            "$limit": 10,
        }

        data = self._fetch(params)

        if not data:
            return VehiculosResult(placa=placa, total=0)

        first = data[0]
        return VehiculosResult(
            placa=str(first.get("placa", placa)),
            clase=str(first.get("clase", "")),
            marca=str(first.get("marca", "")),
            modelo=str(first.get("modelo", "")),
            servicio=str(first.get("servicio", "")),
            cilindraje=int(first.get("cilindraje", 0) or 0),
            resultados=data,
            total=len(data),
        )

    def _query_by_brand(self, marca: str) -> VehiculosResult:
        """Query by brand name."""
        params = {
            "$where": f"marca='{marca}'",
            "$limit": 100,
        }

        data = self._fetch(params)

        if not data:
            return VehiculosResult(marca=marca, total=0)

        first = data[0]
        return VehiculosResult(
            marca=marca,
            clase=str(first.get("clase", "")),
            modelo=str(first.get("modelo", "")),
            servicio=str(first.get("servicio", "")),
            resultados=data,
            total=len(data),
        )

    def _fetch(self, params: dict) -> list[dict]:
        """Fetch data from the datos.gov.co API."""
        import httpx

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(API_URL, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as e:
            raise SourceError(
                "co.vehiculos",
                f"Request timed out after {self._timeout}s: {e}",
            ) from e
        except httpx.HTTPStatusError as e:
            raise SourceError(
                "co.vehiculos",
                f"API returned HTTP {e.response.status_code}: {e.response.text[:200]}",
            ) from e
        except httpx.RequestError as e:
            raise SourceError(
                "co.vehiculos",
                f"Connection error: {e}",
            ) from e
        except Exception as e:
            raise SourceError("co.vehiculos", f"Query failed: {e}") from e

        if not isinstance(data, list):
            raise SourceError(
                "co.vehiculos",
                f"Unexpected response format (expected list, got {type(data).__name__})",
            )

        return data
