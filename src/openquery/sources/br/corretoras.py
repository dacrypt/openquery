"""Brazil CVM corretoras source — stock broker registry via BrasilAPI.

Queries BrasilAPI for CVM-registered stock brokers by CNPJ.
Free REST API, no auth, no CAPTCHA.

API: https://brasilapi.com.br/api/cvm/corretoras/v1/{cnpj}
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.corretoras import BrCorretoraResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://brasilapi.com.br/api/cvm/corretoras/v1"


@register
class BrCorretorasSource(BaseSource):
    """Query Brazilian stock broker registry (CVM) via BrasilAPI."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.corretoras",
            display_name="CVM — Corretoras de Valores",
            description="Brazilian stock broker registry: name, status, CVM code, equity (BrasilAPI/CVM)",  # noqa: E501
            country="BR",
            url="https://brasilapi.com.br/",
            supported_inputs=[DocumentType.NIT, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cnpj = input.extra.get("cnpj", "") or input.document_number
        if not cnpj:
            raise SourceError("br.corretoras", "CNPJ is required")
        cnpj_clean = cnpj.replace(".", "").replace("/", "").replace("-", "").strip()
        return self._query(cnpj_clean)

    def _query(self, cnpj: str) -> BrCorretoraResult:
        try:
            logger.info("Querying BrasilAPI CVM corretora: %s", cnpj)
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{API_URL}/{cnpj}")
                resp.raise_for_status()
                data = resp.json()

            return BrCorretoraResult(
                queried_at=datetime.now(),
                cnpj=data.get("cnpj", cnpj),
                nome_social=data.get("nome_social", ""),
                nome_comercial=data.get("nome_comercial", ""),
                status=data.get("status", ""),
                email=data.get("email", "") or "",
                telefone=data.get("telefone", "") or "",
                municipio=data.get("municipio", ""),
                uf=data.get("uf", ""),
                codigo_cvm=data.get("codigo_cvm", ""),
                valor_patrimonio_liquido=str(data.get("valor_patrimonio_liquido", "")),
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise SourceError("br.corretoras", f"CNPJ {cnpj} not found in CVM") from e
            raise SourceError("br.corretoras", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("br.corretoras", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("br.corretoras", f"Query failed: {e}") from e
