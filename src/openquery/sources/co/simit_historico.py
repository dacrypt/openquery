"""SIMIT Historico source — Colombian historical traffic fines via Socrata API.

Queries Colombia's open data portal (datos.gov.co) for historical
traffic citations/fines by plate number. No browser or CAPTCHA required.

API: https://www.datos.gov.co/resource/72nf-y4v3.json
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.simit_historico import SimitCitacion, SimitHistoricoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.datos.gov.co/resource/72nf-y4v3.json"


@register
class SimitHistoricoSource(BaseSource):
    """Query Colombian historical traffic fines from SIMIT (datos.gov.co)."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.simit_historico",
            display_name="SIMIT Histórico — Multas de Tránsito",
            description="Colombian historical traffic fines from SIMIT open data (datos.gov.co)",
            url="https://www.datos.gov.co/Transporte/SIMIT/72nf-y4v3",
            country="CO",
            supported_inputs=[DocumentType.PLATE, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        placa = input.extra.get("placa", "") or input.document_number
        if not placa:
            raise SourceError("co.simit_historico", "Plate number is required")

        where = f"upper(placa)='{placa.upper().strip()}'"
        return self._fetch(where, placa)

    def _fetch(self, where_clause: str, query_label: str) -> SimitHistoricoResult:
        try:
            params = {"$where": where_clause, "$limit": "100"}
            logger.info("Querying SIMIT historico: %s", where_clause)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            logger.info("Received %d SIMIT historical records", len(data))

            citaciones = []
            for row in data:
                citaciones.append(
                    SimitCitacion(
                        numero=row.get("placa", ""),
                        fecha=row.get("fecha_multa", ""),
                        infraccion=row.get("vigencia", ""),
                        estado=row.get("pagado_si_no", ""),
                        valor=row.get("valor_multa", ""),
                        secretaria=f"{row.get('ciudad', '')}, {row.get('departamento', '')}",
                    )
                )

            return SimitHistoricoResult(
                query=query_label,
                total=len(citaciones),
                citaciones=citaciones,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "co.simit_historico", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("co.simit_historico", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("co.simit_historico", f"Query failed: {e}") from e
