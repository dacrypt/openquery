"""Peajes source — Colombian toll booth tariffs via Socrata API.

Queries Colombia's open data portal (datos.gov.co) for toll tariffs.
No browser or CAPTCHA required — direct HTTP API.

API: https://www.datos.gov.co/resource/7gj8-j6i3.json
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.peajes import PeajeResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.datos.gov.co/resource/7gj8-j6i3.json"


@register
class PeajesSource(BaseSource):
    """Query Colombian toll booth tariffs from datos.gov.co."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.peajes",
            display_name="Peajes — Tarifas de Peajes",
            description="Colombian toll booth tariffs from datos.gov.co (Socrata API)",
            country="CO",
            url=API_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query toll tariffs, optionally filtered by toll name."""
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("co.peajes", f"Unsupported input type: {input.document_type}")

        peaje_name = input.extra.get("peaje", "").strip().upper()

        try:
            params: dict[str, str] = {"$limit": "100"}
            if peaje_name:
                params["$where"] = f"peaje='{peaje_name}'"
                logger.info("Querying tolls for peaje=%s", peaje_name)
            else:
                logger.info("Querying all tolls (limit 100)")

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            logger.info("Received %d toll records", len(data))

            result = PeajeResult(
                peaje=peaje_name,
                resultados=data,
                total=len(data),
            )

            # Populate top-level fields from first result if filtering by name
            if peaje_name and data:
                first = data[0]
                result.categoria = str(first.get("categoria", ""))
                result.valor = int(first.get("valor", 0))
                result.fecha_actualizacion = str(first.get("fecha_actualizacion", ""))

            return result

        except httpx.HTTPStatusError as e:
            raise SourceError("co.peajes", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("co.peajes", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("co.peajes", f"Query failed: {e}") from e
