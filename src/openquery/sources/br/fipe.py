"""Brazil FIPE source — vehicle reference prices via BrasilAPI.

Queries BrasilAPI for FIPE (Fundação Instituto de Pesquisas Econômicas)
vehicle reference prices. Free REST API, no auth, no CAPTCHA.

API: https://brasilapi.com.br/api/fipe/preco/v1/{codigoFipe}
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.fipe import BrFipeResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://brasilapi.com.br/api/fipe/preco/v1"


@register
class BrFipeSource(BaseSource):
    """Query Brazilian vehicle reference prices (FIPE) via BrasilAPI."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.fipe",
            display_name="FIPE — Preço de Veículos",
            description="Brazilian vehicle reference prices from FIPE table (BrasilAPI)",
            country="BR",
            url="https://brasilapi.com.br/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        codigo = input.extra.get("codigo_fipe", "") or input.document_number
        if not codigo:
            raise SourceError("br.fipe", "Código FIPE is required (e.g., '001004-9')")
        return self._query(codigo.strip())

    def _query(self, codigo: str) -> BrFipeResult:
        try:
            logger.info("Querying BrasilAPI FIPE: %s", codigo)
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{API_URL}/{codigo}")
                resp.raise_for_status()
                data = resp.json()

            if isinstance(data, list) and data:
                entry = data[0]
            elif isinstance(data, dict):
                entry = data
            else:
                return BrFipeResult(queried_at=datetime.now(), codigo_fipe=codigo)

            return BrFipeResult(
                queried_at=datetime.now(),
                codigo_fipe=entry.get("codigoFipe", codigo),
                marca=entry.get("marca", ""),
                modelo=entry.get("modelo", ""),
                ano=str(entry.get("anoModelo", "")),
                combustivel=entry.get("combustivel", ""),
                valor=entry.get("valor", ""),
                mes_referencia=entry.get("mesReferencia", ""),
                tipo_veiculo=entry.get("tipoVeiculo", 0),
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return BrFipeResult(queried_at=datetime.now(), codigo_fipe=codigo)
            raise SourceError("br.fipe", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("br.fipe", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("br.fipe", f"Query failed: {e}") from e
