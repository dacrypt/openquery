"""DANE source — Colombian statistics API.

Queries the DANE (Departamento Administrativo Nacional de Estadística)
open data API for statistical indicators.

API: https://www.dane.gov.co/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.dane import DaneResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DANE_API_URL = "https://www.dane.gov.co/files/investigaciones/condiciones_vida/pobreza/"
DANE_URL = "https://www.dane.gov.co/"


@register
class DaneSource(BaseSource):
    """Query DANE (Colombian statistics agency) indicators."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.dane",
            display_name="DANE — Estadísticas Nacionales",
            description="DANE statistical indicators: demographic, economic, and social data for Colombia",  # noqa: E501
            country="CO",
            url=DANE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        indicator = (
            input.extra.get("indicator", "")
            or input.document_number
        ).strip()
        if not indicator:
            raise SourceError("co.dane", "Indicator required (pass via extra.indicator or document_number)")  # noqa: E501
        return self._query(indicator)

    def _query(self, indicator: str) -> DaneResult:
        # Use DANE's open SOCRATA-compatible API for datasets
        api_url = "https://www.datos.gov.co/resource/gt2j-8ykr.json"
        params = {
            "$q": indicator,
            "$limit": "5",
        }

        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                resp = client.get(api_url, params=params)
                if resp.status_code in (404, 400):
                    return DaneResult(
                        queried_at=datetime.now(),
                        indicator=indicator,
                        value="",
                        period="",
                        details={"message": "No data found for this indicator"},
                    )
                resp.raise_for_status()
                data = resp.json()

        except httpx.HTTPStatusError as e:
            raise SourceError("co.dane", f"DANE API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("co.dane", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("co.dane", f"Query failed: {e}") from e

        return self._parse_response(indicator, data)

    def _parse_response(self, indicator: str, data: list | dict) -> DaneResult:
        result = DaneResult(queried_at=datetime.now(), indicator=indicator)

        items = data if isinstance(data, list) else [data]
        if items:
            first = items[0]
            result.value = str(first.get("valor", first.get("value", "")))
            result.period = str(first.get("periodo", first.get("period", first.get("año", ""))))
            result.details = {"total_records": len(items), "first_record": first}

        return result
