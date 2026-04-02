"""Brazil CNPJ source — business registry via BrasilAPI.

Queries BrasilAPI for CNPJ (Cadastro Nacional da Pessoa Jurídica)
business registration data. Free REST API, no auth, no CAPTCHA.

API: https://brasilapi.com.br/api/cnpj/v1/{cnpj}
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.cnpj import BrCnpjResult, CnpjSocio
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://brasilapi.com.br/api/cnpj/v1"


@register
class BrCnpjSource(BaseSource):
    """Query Brazilian business registry (CNPJ) via BrasilAPI."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.cnpj",
            display_name="CNPJ — Cadastro Nacional da Pessoa Jurídica",
            description="Brazilian business registry: company name, status, CNAE, partners, address",
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
            raise SourceError("br.cnpj", "CNPJ is required (14 digits)")
        cnpj_clean = cnpj.replace(".", "").replace("/", "").replace("-", "").strip()
        if len(cnpj_clean) != 14 or not cnpj_clean.isdigit():
            raise SourceError("br.cnpj", f"Invalid CNPJ: must be 14 digits, got '{cnpj}'")
        return self._query(cnpj_clean)

    def _query(self, cnpj: str) -> BrCnpjResult:
        try:
            logger.info("Querying BrasilAPI CNPJ: %s", cnpj)
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{API_URL}/{cnpj}")
                resp.raise_for_status()
                data = resp.json()

            socios = []
            for s in data.get("qsa", []):
                socios.append(CnpjSocio(
                    nome=s.get("nome_socio", ""),
                    cnpj_cpf_do_socio=s.get("cnpj_cpf_do_socio", ""),
                    qualificacao_socio=s.get("qualificacao_socio", ""),
                    data_entrada_sociedade=s.get("data_entrada_sociedade", ""),
                ))

            # Helper to safely get string (BrasilAPI returns None for missing fields)
            def s(key: str, alt: str = "") -> str:
                v = data.get(key, alt)
                return str(v) if v is not None else ""

            return BrCnpjResult(
                queried_at=datetime.now(),
                cnpj=s("cnpj", cnpj),
                razao_social=s("razao_social"),
                nome_fantasia=s("nome_fantasia"),
                situacao_cadastral=s("descricao_situacao_cadastral"),
                data_situacao_cadastral=s("data_situacao_cadastral"),
                cnae_fiscal=s("cnae_fiscal"),
                cnae_fiscal_descricao=s("cnae_fiscal_descricao"),
                natureza_juridica=s("descricao_natureza_juridica"),
                porte=s("porte") or s("descricao_porte"),
                uf=s("uf"),
                municipio=s("municipio"),
                logradouro=s("logradouro"),
                numero=s("numero"),
                bairro=s("bairro"),
                cep=s("cep"),
                telefone=s("ddd_telefone_1"),
                email=s("email"),
                data_inicio_atividade=s("data_inicio_atividade"),
                socios=socios,
                total_socios=len(socios),
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise SourceError("br.cnpj", f"CNPJ {cnpj} not found") from e
            raise SourceError("br.cnpj", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("br.cnpj", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("br.cnpj", f"Query failed: {e}") from e
