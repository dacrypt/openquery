"""Brazil CEP source — zip code lookup via BrasilAPI.

Queries BrasilAPI for CEP (Código de Endereçamento Postal) data.
Free REST API, no auth, no CAPTCHA.

API: https://brasilapi.com.br/api/cep/v2/{cep}
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.cep import BrCepResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://brasilapi.com.br/api/cep/v2"


@register
class BrCepSource(BaseSource):
    """Query Brazilian zip codes (CEP) via BrasilAPI."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.cep",
            display_name="CEP — Consulta de CEP",
            description="Brazilian zip code lookup: city, state, neighborhood, street (BrasilAPI)",
            country="BR",
            url="https://brasilapi.com.br/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cep = input.extra.get("cep", "") or input.document_number
        if not cep:
            raise SourceError("br.cep", "CEP is required (8 digits, e.g., '01001000')")
        cep_clean = cep.replace("-", "").replace(".", "").strip()
        return self._query(cep_clean)

    def _query(self, cep: str) -> BrCepResult:
        try:
            logger.info("Querying BrasilAPI CEP: %s", cep)
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{API_URL}/{cep}")
                resp.raise_for_status()
                data = resp.json()

            return BrCepResult(
                queried_at=datetime.now(),
                cep=data.get("cep", cep),
                estado=data.get("state", ""),
                cidade=data.get("city", ""),
                bairro=data.get("neighborhood", ""),
                logradouro=data.get("street", ""),
                complemento=data.get("complement", "") or "",
                ibge=data.get("ibge", ""),
                ddd=data.get("ddd", "") or "",
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise SourceError("br.cep", f"CEP {cep} not found") from e
            raise SourceError("br.cep", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("br.cep", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("br.cep", f"Query failed: {e}") from e
