"""Brazil NCM source — product classification for trade/customs via BrasilAPI.

Free REST API, no auth, no CAPTCHA.

API: https://brasilapi.com.br/api/ncm/v1?search={query}
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.ncm import BrNcmResult, NcmItem
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://brasilapi.com.br/api/ncm/v1"


@register
class BrNcmSource(BaseSource):
    """Query Brazilian product classification codes (NCM) via BrasilAPI."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.ncm",
            display_name="NCM — Nomenclatura Comum do Mercosul",
            description="Brazilian product classification codes for trade/customs (BrasilAPI/NCM)",
            country="BR",
            url="https://brasilapi.com.br/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        q = input.extra.get("q", "") or input.document_number
        if not q:
            raise SourceError("br.ncm", "Search query is required (product name or NCM code)")
        return self._query(q.strip())

    def _query(self, q: str) -> BrNcmResult:
        try:
            logger.info("Querying BrasilAPI NCM: %s", q)
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL, params={"search": q})
                resp.raise_for_status()
                data = resp.json()

            itens = [
                NcmItem(
                    codigo=item.get("codigo", ""),
                    descricao=item.get("descricao", ""),
                    data_inicio=item.get("data_inicio", ""),
                    data_fim=item.get("data_fim", ""),
                )
                for item in data[:50]
            ]

            return BrNcmResult(
                queried_at=datetime.now(),
                query=q,
                total=len(itens),
                itens=itens,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("br.ncm", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("br.ncm", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("br.ncm", f"Query failed: {e}") from e
