"""Chile Mindicador source — economic indicators.

Queries mindicador.cl for Chilean economic indicators (UF, USD, EUR, UTM, IPC).
Free community REST API, no auth, no CAPTCHA.

API: https://mindicador.cl/api
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.mindicador import ClMindicadorResult, Indicador
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://mindicador.cl/api"


@register
class ClMindicadorSource(BaseSource):
    """Query Chilean economic indicators (UF, USD, EUR) via mindicador.cl."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.mindicador",
            display_name="Mindicador — Indicadores Económicos Chile",
            description="Chilean economic indicators: UF, USD/CLP, EUR/CLP, UTM, IPC (mindicador.cl)",
            country="CL",
            url="https://mindicador.cl/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        indicator = input.extra.get("indicador", "") or input.document_number
        return self._query(indicator.strip() if indicator else "")

    def _query(self, indicator: str = "") -> ClMindicadorResult:
        try:
            url = f"{API_URL}/{indicator}" if indicator else API_URL
            logger.info("Querying mindicador.cl: %s", url)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()

            # If querying all indicators (no specific one)
            if not indicator or "serie" not in data:
                indicadores = []
                uf = dolar = euro = utm = ipc = 0.0

                for key, val in data.items():
                    if isinstance(val, dict) and "valor" in val:
                        indicadores.append(Indicador(
                            codigo=val.get("codigo", key),
                            nombre=val.get("nombre", ""),
                            unidad=val.get("unidad_medida", ""),
                            valor=float(val.get("valor", 0) or 0),
                            fecha=val.get("fecha", ""),
                        ))
                        if key == "uf":
                            uf = float(val.get("valor", 0) or 0)
                        elif key == "dolar":
                            dolar = float(val.get("valor", 0) or 0)
                        elif key == "euro":
                            euro = float(val.get("valor", 0) or 0)
                        elif key == "utm":
                            utm = float(val.get("valor", 0) or 0)
                        elif key == "ipc":
                            ipc = float(val.get("valor", 0) or 0)

                return ClMindicadorResult(
                    queried_at=datetime.now(),
                    query=indicator or "all",
                    uf=uf,
                    dolar=dolar,
                    euro=euro,
                    utm=utm,
                    ipc=ipc,
                    total_indicadores=len(indicadores),
                    indicadores=indicadores,
                )
            else:
                # Specific indicator with time series
                serie = data.get("serie", [])
                indicadores = []
                for entry in serie[:30]:
                    indicadores.append(Indicador(
                        codigo=data.get("codigo", indicator),
                        nombre=data.get("nombre", ""),
                        unidad=data.get("unidad_medida", ""),
                        valor=float(entry.get("valor", 0) or 0),
                        fecha=entry.get("fecha", ""),
                    ))

                return ClMindicadorResult(
                    queried_at=datetime.now(),
                    query=indicator,
                    total_indicadores=len(indicadores),
                    indicadores=indicadores,
                )

        except httpx.HTTPStatusError as e:
            raise SourceError("cl.mindicador", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("cl.mindicador", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("cl.mindicador", f"Query failed: {e}") from e
