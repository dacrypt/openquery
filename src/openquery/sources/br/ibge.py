"""Brazil IBGE source — states and municipalities via BrasilAPI.

Queries BrasilAPI for IBGE geographic data.
Free REST API, no auth, no CAPTCHA.

API: https://brasilapi.com.br/api/ibge/uf/v1
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.ibge import BrIbgeResult, IbgeUF
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://brasilapi.com.br/api/ibge/uf/v1"


@register
class BrIbgeSource(BaseSource):
    """Query Brazilian states/municipalities (IBGE) via BrasilAPI."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.ibge",
            display_name="IBGE — Estados e Regiões",
            description="Brazilian states and regions from IBGE geographic data (BrasilAPI)",
            country="BR",
            url="https://brasilapi.com.br/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        uf = input.extra.get("uf", "") or input.document_number
        if uf and len(uf) == 2:
            return self._query_uf(uf.upper())
        return self._query_all()

    def _query_all(self) -> BrIbgeResult:
        try:
            logger.info("Querying IBGE all states")
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL)
                resp.raise_for_status()
                data = resp.json()

            estados = []
            for s in data:
                regiao = s.get("regiao", {})
                estados.append(IbgeUF(
                    id=s.get("id", 0),
                    sigla=s.get("sigla", ""),
                    nome=s.get("nome", ""),
                    regiao=regiao.get("nome", "") if isinstance(regiao, dict) else str(regiao),
                ))

            return BrIbgeResult(
                queried_at=datetime.now(),
                query="all",
                total=len(estados),
                estados=estados,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("br.ibge", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("br.ibge", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("br.ibge", f"Query failed: {e}") from e

    def _query_uf(self, uf: str) -> BrIbgeResult:
        try:
            logger.info("Querying IBGE state: %s", uf)
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{API_URL}/{uf}")
                resp.raise_for_status()
                data = resp.json()

            regiao = data.get("regiao", {})
            estado = IbgeUF(
                id=data.get("id", 0),
                sigla=data.get("sigla", ""),
                nome=data.get("nome", ""),
                regiao=regiao.get("nome", "") if isinstance(regiao, dict) else str(regiao),
            )

            return BrIbgeResult(
                queried_at=datetime.now(),
                query=uf,
                total=1,
                estados=[estado],
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("br.ibge", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("br.ibge", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("br.ibge", f"Query failed: {e}") from e
