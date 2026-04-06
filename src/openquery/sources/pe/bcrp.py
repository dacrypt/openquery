"""Peru BCRP source — central bank exchange rates and statistics.

Queries BCRP (Banco Central de Reserva del Perú) for economic series.
Free REST API, no auth, no CAPTCHA.

API: https://estadisticas.bcrp.gob.pe/estadisticas/series/api/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.bcrp import BcrpDataPoint, PeBcrpResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"

SERIES_MAP = {
    "tipo_cambio": "PD04637PD",
    "inflacion": "PD38073PM",
    "pbi": "PM05373MA",
}


@register
class PeBcrpSource(BaseSource):
    """Query Peruvian central bank exchange rates (BCRP)."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.bcrp",
            display_name="BCRP — Tipo de Cambio y Estadísticas",
            description="Peru central bank exchange rates and economic statistics (BCRP API)",
            country="PE",
            url="https://estadisticas.bcrp.gob.pe/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        serie = input.extra.get("serie", "") or input.document_number or "tipo_cambio"
        serie_id = SERIES_MAP.get(serie.lower(), serie)
        return self._query(serie_id)

    def _query(self, serie_id: str) -> PeBcrpResult:
        try:
            url = f"{API_URL}/{serie_id}/json"
            logger.info("Querying BCRP: %s", serie_id)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()

            config = data.get("config", {})
            titulo = config.get("title", "")
            periods = data.get("periods", [])

            datos = []
            for p in periods[-30:]:
                valores = p.get("values", [])
                datos.append(
                    BcrpDataPoint(
                        fecha=p.get("name", ""),
                        valor=valores[0] if valores else "",
                    )
                )

            ultimo = datos[-1] if datos else BcrpDataPoint()

            return PeBcrpResult(
                queried_at=datetime.now(),
                serie=serie_id,
                titulo=titulo,
                ultimo_valor=ultimo.valor,
                ultima_fecha=ultimo.fecha,
                total_datos=len(datos),
                datos=datos,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("pe.bcrp", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("pe.bcrp", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("pe.bcrp", f"Query failed: {e}") from e
