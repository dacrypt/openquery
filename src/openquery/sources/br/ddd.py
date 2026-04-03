"""Brazil DDD source — area code lookup via BrasilAPI.

Queries BrasilAPI for DDD (Discagem Direta a Distância) area code info.
Free REST API, no auth, no CAPTCHA.

API: https://brasilapi.com.br/api/ddd/v1/{ddd}
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.ddd import BrDddResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://brasilapi.com.br/api/ddd/v1"


@register
class BrDddSource(BaseSource):
    """Query Brazilian area code info (DDD) via BrasilAPI."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.ddd",
            display_name="DDD — Código de Área",
            description="Brazilian area code lookup: state and cities for a DDD code (BrasilAPI)",
            country="BR",
            url="https://brasilapi.com.br/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        ddd = input.extra.get("ddd", "") or input.document_number
        if not ddd:
            raise SourceError("br.ddd", "DDD code is required (e.g., '11' for São Paulo)")
        return self._query(ddd.strip())

    def _query(self, ddd: str) -> BrDddResult:
        try:
            logger.info("Querying BrasilAPI DDD: %s", ddd)
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{API_URL}/{ddd}")
                resp.raise_for_status()
                data = resp.json()

            cities = data.get("cities", [])

            return BrDddResult(
                queried_at=datetime.now(),
                ddd=ddd,
                state=data.get("state", ""),
                cities=cities[:50],
                total_cities=len(cities),
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise SourceError("br.ddd", f"DDD {ddd} not found") from e
            raise SourceError("br.ddd", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("br.ddd", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("br.ddd", f"Query failed: {e}") from e
