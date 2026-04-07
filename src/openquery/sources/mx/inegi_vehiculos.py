"""INEGI vehicle registration statistics source — Mexico BIE API.

Queries the INEGI BIE (Banco de Información Económica) API for vehicle
registration indicators in Mexico.

Requires an INEGI API token (free registration at
https://www.inegi.org.mx/servicios/api_biinegi.html).
Set OPENQUERY_INEGI_API_KEY to your token.

API: https://www.inegi.org.mx/app/api/indicadores/desarrolladores/jsonxml/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.inegi_vehiculos import InegiVehiculoDataPoint, InegiVehiculosResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL_TEMPLATE = (
    "https://www.inegi.org.mx/app/api/indicadores/desarrolladores/jsonxml"
    "/INDICATOR/{indicator}/es/0700/false/BIE/2.0/{token}?type=json"
)

# Default: registered motor vehicles (INEGI indicator for total vehicle registrations)
DEFAULT_INDICATOR = "6207019014"


@register
class InegiVehiculosSource(BaseSource):
    """Query INEGI vehicle registration statistics via BIE API."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.inegi_vehiculos",
            display_name="INEGI — Estadísticas de Vehículos Registrados",
            description=(
                "Mexico INEGI BIE API: vehicle registration statistics and indicators. "
                "Requires OPENQUERY_INEGI_API_KEY (free registration at inegi.org.mx)"
            ),
            country="MX",
            url="https://www.inegi.org.mx/app/indicadores/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        indicator = input.extra.get("indicator", DEFAULT_INDICATOR).strip()
        if not indicator:
            indicator = DEFAULT_INDICATOR

        from openquery.config import get_settings

        settings = get_settings()
        token = input.extra.get("api_key", settings.inegi_api_key or "").strip()

        if not token:
            raise SourceError(
                "mx.inegi_vehiculos",
                "INEGI API key required. Set OPENQUERY_INEGI_API_KEY or pass extra.api_key. "
                "Register free at https://www.inegi.org.mx/servicios/api_biinegi.html",
            )

        return self._fetch(indicator, token)

    def _fetch(self, indicator: str, token: str) -> InegiVehiculosResult:
        url = API_URL_TEMPLATE.format(indicator=indicator, token=token)
        try:
            logger.info("Querying INEGI vehiculos: indicator=%s", indicator)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()

            # INEGI BIE response structure:
            # {"Series": [{"INDICADOR": "...", "DESC_INDICADOR": "...", "OBSERVATIONS": [...]}]}
            series_list = data.get("Series", [])
            if not series_list:
                raise SourceError("mx.inegi_vehiculos", "No series data in response")

            series = series_list[0]
            indicator_name = series.get("DESC_INDICADOR", "")
            observations = series.get("OBSERVATIONS", [])

            data_points: list[InegiVehiculoDataPoint] = []
            for obs in observations:
                raw_val = obs.get("OBS_VALUE", "")
                value_str = "" if raw_val is None else str(raw_val)
                period = str(obs.get("TIME_PERIOD", "") or "")
                data_points.append(
                    InegiVehiculoDataPoint(
                        period=period,
                        value=value_str,
                    )
                )

            return InegiVehiculosResult(
                queried_at=datetime.now(),
                indicator=indicator,
                indicator_name=indicator_name,
                total_observations=len(data_points),
                data_points=data_points,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "mx.inegi_vehiculos", f"INEGI API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("mx.inegi_vehiculos", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("mx.inegi_vehiculos", f"Query failed: {e}") from e
