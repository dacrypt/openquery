"""Receita Federal MEI microentrepreneur source — Brazil.

Queries Receita Federal for MEI (Microempreendedor Individual) status by CNPJ.

URL: https://www.gov.br/empresas-e-negocios/pt-br/empreendedor
Input: CNPJ
Returns: MEI status, name
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.receita_mei import ReceitaMeiResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MEI_API_URL = "https://publica.cnpj.ws/cnpj/{cnpj}"


@register
class ReceitaMeiSource(BaseSource):
    """Query Receita Federal for MEI status by CNPJ."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.receita_mei",
            display_name="Receita Federal — MEI (Microempreendedor Individual)",
            description="Brazil Receita Federal MEI status lookup by CNPJ",
            country="BR",
            url="https://www.gov.br/empresas-e-negocios/pt-br/empreendedor",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cnpj = (input.extra.get("cnpj", "") or input.document_number).strip()
        cnpj = cnpj.replace(".", "").replace("/", "").replace("-", "")
        if not cnpj:
            raise SourceError("br.receita_mei", "CNPJ required (extra.cnpj or document_number)")
        return self._fetch(cnpj)

    def _fetch(self, cnpj: str) -> ReceitaMeiResult:
        try:
            logger.info("Querying Receita MEI: cnpj=%s", cnpj)
            url = MEI_API_URL.format(cnpj=cnpj)
            headers = {"User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)"}
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()

            nome = data.get("razao_social", "")
            opcoes_simples = data.get("simples", {}) or {}
            mei_status = "MEI" if data.get("descricao_porte", "").upper() == "MICRO EMPRESA" and opcoes_simples.get("simei_optante") else "Não MEI"  # noqa: E501

            return ReceitaMeiResult(
                queried_at=datetime.now(),
                cnpj=cnpj,
                nome=nome,
                mei_status=mei_status,
                details=f"CNPJ: {cnpj} — {nome}",
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("br.receita_mei", f"API returned HTTP {e.response.status_code}") from e  # noqa: E501
        except httpx.RequestError as e:
            raise SourceError("br.receita_mei", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("br.receita_mei", f"Query failed: {e}") from e
