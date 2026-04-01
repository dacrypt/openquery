"""Tarifas de Energia source — Colombian electricity tariffs via Socrata API.

Queries Colombia's open data portal (datos.gov.co) for electricity tariffs
from SUI/SSPD. No browser or CAPTCHA required — direct HTTP API.

API: https://www.datos.gov.co/resource/bshp-gbss.json
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

API_URL = "https://www.datos.gov.co/resource/bshp-gbss.json"
PAGE_URL = "https://www.datos.gov.co/"


@register
class TarifasEnergiaSource(BaseSource):
    """Query Colombian electricity tariffs from datos.gov.co."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.tarifas_energia",
            display_name="SUI \u2014 Tarifas de Energ\u00eda El\u00e9ctrica",
            description="Colombian electricity tariffs from SUI/SSPD (datos.gov.co)",
            country="CO",
            url=PAGE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query electricity tariffs by municipio or estrato."""
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError(
                "co.tarifas_energia",
                f"Unsupported input type: {input.document_type}",
            )

        municipio = input.extra.get("municipio", "").strip().upper()
        estrato = input.extra.get("estrato", "").strip()

        if not municipio and not estrato:
            raise SourceError(
                "co.tarifas_energia",
                "Must provide extra['municipio'] or extra['estrato']",
            )

        try:
            conditions = []
            if municipio:
                prefix = municipio[:5]
                conditions.append(
                    f"starts_with(upper(municipio), '{prefix}')"
                )
            if estrato:
                conditions.append(f"estrato='{estrato}'")

            where_clause = " AND ".join(conditions)
            params: dict[str, str] = {"$where": where_clause, "$limit": "500"}

            logger.info("Querying electricity tariffs: %s", where_clause)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            logger.info("Received %d tariff records", len(data))

            tarifas = []
            for row in data:
                tarifas.append(TarifaEnergia(
                    estrato=row.get("estrato", ""),
                    componente=row.get("componente", row.get("concepto", "")),
                    valor_kwh=row.get("valor_kwh", row.get("tarifa", "")),
                    empresa=row.get("empresa", row.get("prestador", "")),
                    departamento=row.get("departamento", ""),
                    municipio=row.get("municipio", ""),
                ))

            query_desc = municipio or f"estrato {estrato}"

            return NuptseResult(
                query=query_desc,
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
