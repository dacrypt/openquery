"""Brazil Receita CNAE source — IBGE activity classification codes via BrasilAPI.

Free REST API, no auth, no CAPTCHA.

API: https://brasilapi.com.br/api/cnae/v1/{code}
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.receita_cnae import BrReceitaCnaeResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://brasilapi.com.br/api/cnae/v1"


@register
class BrReceitaCnaeSource(BaseSource):
    """Query Brazilian CNAE activity classification codes via BrasilAPI."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.receita_cnae",
            display_name="Receita Federal — CNAE (Classificação Nacional de Atividades Econômicas)",
            description="Brazilian CNAE economic activity codes via BrasilAPI (IBGE/Receita Federal)",  # noqa: E501
            country="BR",
            url="https://brasilapi.com.br/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        code = (input.extra.get("code", "") or input.document_number).strip()
        if not code:
            raise SourceError("br.receita_cnae", "CNAE code is required (e.g. '6201500')")
        return self._query(code)

    def _query(self, code: str) -> BrReceitaCnaeResult:
        try:
            logger.info("Querying BrasilAPI CNAE: %s", code)
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{API_URL}/{code}")
                if resp.status_code == 404:
                    return BrReceitaCnaeResult(
                        queried_at=datetime.now(),
                        code=code,
                        details={"error": "CNAE code not found"},
                    )
                resp.raise_for_status()
                data = resp.json()

            return BrReceitaCnaeResult(
                queried_at=datetime.now(),
                code=data.get("codigo", code),
                description=data.get("descricao", ""),
                section=data.get("secao", ""),
                division=data.get("divisao", ""),
                details={k: v for k, v in data.items() if k not in ("codigo", "descricao")},
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "br.receita_cnae", f"API returned HTTP {e.response.status_code}"
            ) from e  # noqa: E501
        except httpx.RequestError as e:
            raise SourceError("br.receita_cnae", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("br.receita_cnae", f"Query failed: {e}") from e
