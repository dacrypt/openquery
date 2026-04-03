"""Argentina economic series source — datos.gob.ar time series API.

Queries Argentina's open data time series API for economic indicators
(exchange rates, inflation, employment, etc.). Free REST API, no auth.

API: https://apis.datos.gob.ar/series/api/series/
Docs: https://datosgobar.github.io/series-tiempo-ar-api/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.series import ArSeriesResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://apis.datos.gob.ar/series/api/series/"

# Common series IDs
SERIES_MAP = {
    "dolar": "168.1_T_CAMBIOR_D_0_0_26",
    "inflacion": "148.3_INIDINGS_DICI_M_26",
    "desempleo": "42.3_TDESam_0_M_29",
    "pib": "11.3_VMATAM_2004_T_17",
}


@register
class ArSeriesSource(BaseSource):
    """Query Argentine economic indicators (datos.gob.ar time series)."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.series",
            display_name="Series de Tiempo — Indicadores Económicos",
            description="Argentine economic time series: exchange rates, inflation, GDP (datos.gob.ar API)",
            country="AR",
            url="https://apis.datos.gob.ar/series/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        serie = input.extra.get("serie", "") or input.document_number
        if not serie:
            raise SourceError("ar.series", "Serie ID or name required (e.g., 'dolar', 'inflacion')")
        # Map common names to IDs
        serie_id = SERIES_MAP.get(serie.lower(), serie)
        limit = int(input.extra.get("limit", "10"))
        return self._query(serie_id, limit)

    def _query(self, serie_id: str, limit: int = 10) -> ArSeriesResult:
        try:
            params = {"ids": serie_id, "limit": str(limit), "format": "json"}
            logger.info("Querying datos.gob.ar series: %s", serie_id)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            datos = data.get("data", [])
            meta = data.get("meta", [{}])
            serie_meta = meta[0] if meta else {} if not isinstance(meta, list) else {}

            # Extract serie metadata from nested structure
            titulo = ""
            unidades = ""
            fuente = ""
            frecuencia = ""
            if isinstance(meta, list) and meta:
                first_meta = meta[0] if isinstance(meta[0], dict) else {}
                field = first_meta.get("field", {})
                titulo = field.get("description", "")
                unidades = field.get("units", "")
                fuente = field.get("distribution_description", "")
                frecuencia = field.get("frequency", "")

            ultimo = datos[-1] if datos else [None, None]

            return ArSeriesResult(
                queried_at=datetime.now(),
                serie_id=serie_id,
                serie_titulo=titulo,
                serie_unidades=unidades,
                serie_fuente=fuente,
                frecuencia=frecuencia,
                ultimo_valor=float(ultimo[1]) if ultimo and ultimo[1] is not None else 0.0,
                ultima_fecha=str(ultimo[0]) if ultimo else "",
                total_datos=len(datos),
                datos=datos,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("ar.series", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("ar.series", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("ar.series", f"Query failed: {e}") from e
