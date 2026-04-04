"""Brazil feriados source — national holidays via BrasilAPI.

Free REST API, no auth, no CAPTCHA.

API: https://brasilapi.com.br/api/feriados/v1/{year}
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.feriados import BrFeriadosResult, Feriado
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://brasilapi.com.br/api/feriados/v1"


@register
class BrFeriadosSource(BaseSource):
    """Query Brazilian national holidays via BrasilAPI."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.feriados",
            display_name="Feriados — Feriados Nacionais",
            description="Brazilian national holidays by year (BrasilAPI)",
            country="BR",
            url="https://brasilapi.com.br/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        year = input.extra.get("ano", "") or input.document_number or str(datetime.now().year)
        return self._query(int(year))

    def _query(self, year: int) -> BrFeriadosResult:
        try:
            logger.info("Querying BrasilAPI feriados: %d", year)
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{API_URL}/{year}")
                resp.raise_for_status()
                data = resp.json()

            feriados = [
                Feriado(
                    date=f.get("date", ""),
                    name=f.get("name", ""),
                    type=f.get("type", ""),
                )
                for f in data
            ]

            return BrFeriadosResult(
                queried_at=datetime.now(),
                ano=year,
                total=len(feriados),
                feriados=feriados,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("br.feriados", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("br.feriados", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("br.feriados", f"Query failed: {e}") from e
