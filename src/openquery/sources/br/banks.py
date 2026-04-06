"""Brazil banks source — bank info via BrasilAPI.

Queries BrasilAPI for Brazilian bank information by COMPE code.
Free REST API, no auth, no CAPTCHA.

API: https://brasilapi.com.br/api/banks/v1/{code}
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.banks import BrBankResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://brasilapi.com.br/api/banks/v1"


@register
class BrBanksSource(BaseSource):
    """Query Brazilian bank info via BrasilAPI."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.banks",
            display_name="Bancos — Consulta de Bancos",
            description="Brazilian bank information by COMPE code (BrasilAPI/BACEN)",
            country="BR",
            url="https://brasilapi.com.br/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        code = input.extra.get("code", "") or input.document_number
        if not code:
            raise SourceError(
                "br.banks", "Bank COMPE code is required (e.g., '001' for Banco do Brasil)"
            )
        return self._query(code.strip())

    def _query(self, code: str) -> BrBankResult:
        try:
            logger.info("Querying BrasilAPI bank: %s", code)
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{API_URL}/{code}")
                resp.raise_for_status()
                data = resp.json()

            return BrBankResult(
                queried_at=datetime.now(),
                ispb=data.get("ispb", ""),
                name=data.get("name", ""),
                code=data.get("code", 0) or 0,
                full_name=data.get("fullName", ""),
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise SourceError("br.banks", f"Bank code {code} not found") from e
            raise SourceError("br.banks", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("br.banks", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("br.banks", f"Query failed: {e}") from e
