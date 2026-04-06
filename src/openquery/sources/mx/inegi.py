"""Mexico INEGI source — geostatistical catalog.

Queries INEGI for Mexican states and municipalities with population data.
Free REST API, no auth, no CAPTCHA.

API: https://gaia.inegi.org.mx/wscatgeo/v2/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.inegi import InegiEntidad, MxInegiResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://gaia.inegi.org.mx/wscatgeo/v2"


@register
class MxInegiSource(BaseSource):
    """Query Mexican geostatistical catalog (INEGI) — states and municipalities."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.inegi",
            display_name="INEGI — Catálogo Geoestadístico",
            description="Mexican states/municipalities with population data (INEGI Census 2020)",
            country="MX",
            url="https://www.inegi.org.mx/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        state_code = input.extra.get("estado", "") or input.document_number
        if state_code and len(state_code) <= 2:
            return self._query_municipalities(state_code)
        return self._query_states()

    def _query_states(self) -> MxInegiResult:
        try:
            logger.info("Querying INEGI states catalog")
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{API_URL}/mgee")
                resp.raise_for_status()
                data = resp.json()

            datos = data.get("datos", [])
            entidades = []
            for d in datos:
                entidades.append(
                    InegiEntidad(
                        clave=d.get("cve_agee", ""),
                        nombre=d.get("nom_agee", ""),
                        poblacion_total=int(d.get("pob", 0) or 0),
                        poblacion_masculina=int(d.get("pob_mas", 0) or 0),
                        poblacion_femenina=int(d.get("pob_fem", 0) or 0),
                        viviendas=int(d.get("viv", 0) or 0),
                    )
                )

            return MxInegiResult(
                queried_at=datetime.now(),
                query="estados",
                nivel="estados",
                total=len(entidades),
                entidades=entidades,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("mx.inegi", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("mx.inegi", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("mx.inegi", f"Query failed: {e}") from e

    def _query_municipalities(self, state_code: str) -> MxInegiResult:
        try:
            logger.info("Querying INEGI municipalities for state: %s", state_code)
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{API_URL}/mgem/{state_code}")
                resp.raise_for_status()
                data = resp.json()

            datos = data.get("datos", [])
            entidades = []
            for d in datos:
                entidades.append(
                    InegiEntidad(
                        clave=d.get("cve_agem", ""),
                        nombre=d.get("nom_agem", ""),
                        poblacion_total=int(d.get("pob", 0) or 0),
                        poblacion_masculina=int(d.get("pob_mas", 0) or 0),
                        poblacion_femenina=int(d.get("pob_fem", 0) or 0),
                        viviendas=int(d.get("viv", 0) or 0),
                    )
                )

            return MxInegiResult(
                queried_at=datetime.now(),
                query=f"municipios estado {state_code}",
                nivel="municipios",
                total=len(entidades),
                entidades=entidades,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("mx.inegi", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("mx.inegi", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("mx.inegi", f"Query failed: {e}") from e
