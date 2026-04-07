"""Tarifas de Energia source — Colombian electricity tariffs via Socrata API.

Queries Colombia's open data portal (datos.gov.co) for electricity tariffs
from SUI/SSPD by city and estrato (1-6).

Usage:
    openquery query co.tarifas_energia --custom search -e '{"ciudad":"Bogota","estrato":"3"}'
    openquery query co.tarifas_energia --custom search -e '{"ciudad":"Cali"}'
    openquery query co.tarifas_energia --custom search -e '{"operador":"ENEL","estrato":"1"}'

API: https://www.datos.gov.co/resource/ytme-6qnu.json
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.nuptse import NuptseResult, TarifaEnergia
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.datos.gov.co/resource/ytme-6qnu.json"
PAGE_URL = "https://www.datos.gov.co/"

# Map common city names to operator names in the dataset
_CITY_TO_OPERATOR = {
    "bogota": "ENEL",
    "bogotá": "ENEL",
    "cundinamarca": "ENEL",
    "cali": "EMCALI",
    "valle": "CELSIA Colombia - Valle",
    "valle del cauca": "CELSIA Colombia - Valle",
    "tolima": "CELSIA Colombia - Tolima",
    "ibague": "CELSIA Colombia - Tolima",
    "ibagué": "CELSIA Colombia - Tolima",
}

# Map estrato number to nivel filter patterns
_ESTRATO_MAP = {
    "1": "Nivel 1",
    "2": "NIVEL II",
    "3": "NIVEL III",
    "4": "Nivel 4",
    "5": "Nivel 5",
    "6": "Nivel 6",
}


@register
class TarifasEnergiaSource(BaseSource):
    """Query Colombian electricity tariffs by city and estrato."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.tarifas_energia",
            display_name="SUI — Tarifas de Energía Eléctrica",
            description="Colombian electricity tariffs by city/estrato from SUI/SSPD (datos.gov.co)",  # noqa: E501
            country="CO",
            url=PAGE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query electricity tariffs by ciudad, operador, and/or estrato."""
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError(
                "co.tarifas_energia",
                f"Unsupported input type: {input.document_type}",
            )

        ciudad = input.extra.get("ciudad", "").strip().lower()
        operador = input.extra.get("operador", "").strip()
        estrato = input.extra.get("estrato", "").strip()

        if not ciudad and not operador and not estrato:
            raise SourceError(
                "co.tarifas_energia",
                "Provide extra['ciudad'] (e.g. 'Bogota', 'Cali'), "
                "extra['operador'] (e.g. 'ENEL'), or extra['estrato'] (1-6)",
            )

        # Resolve city to operator
        if ciudad and not operador:
            operador = _CITY_TO_OPERATOR.get(ciudad, ciudad)

        # Build Socrata $where clause
        conditions = []
        if operador:
            safe_op = operador.replace("'", "''")
            conditions.append(
                f"upper(operador_de_red) like '%{safe_op.upper()}%'"
            )
        if estrato:
            nivel = _ESTRATO_MAP.get(estrato, f"Nivel {estrato}")
            safe_nivel = nivel.replace("'", "''")
            conditions.append(f"upper(nivel) like '%{safe_nivel.upper()}%'")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        try:
            params: dict[str, str] = {
                "$where": where_clause,
                "$limit": "500",
                "$order": "a_o DESC, periodo DESC",
            }

            logger.info("Querying electricity tariffs: %s", where_clause)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            logger.info("Received %d tariff records", len(data))

            tarifas = []
            for row in data:
                tarifas.append(
                    TarifaEnergia(
                        estrato=row.get("nivel", ""),
                        componente=row.get("periodo", ""),
                        valor_kwh=row.get("cu_total", ""),
                        empresa=row.get("operador_de_red", ""),
                        departamento=row.get("a_o", ""),
                        municipio=row.get("operador_de_red", ""),
                    )
                )

            query_desc = []
            if ciudad:
                query_desc.append(f"ciudad={ciudad}")
            if operador:
                query_desc.append(f"operador={operador}")
            if estrato:
                query_desc.append(f"estrato={estrato}")

            return NuptseResult(
                query=", ".join(query_desc),
                total=len(tarifas),
                tarifas=tarifas,
            )

        except SourceError:
            raise
        except httpx.HTTPStatusError as e:
            msg = f"API returned HTTP {e.response.status_code}"
            raise SourceError("co.tarifas_energia", msg) from e
        except httpx.RequestError as e:
            raise SourceError("co.tarifas_energia", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("co.tarifas_energia", f"Query failed: {e}") from e
