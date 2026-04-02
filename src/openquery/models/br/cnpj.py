"""Brazil CNPJ data model — business registry via BrasilAPI."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CnpjSocio(BaseModel):
    """A partner/shareholder from CNPJ lookup."""

    nome: str = ""
    cnpj_cpf_do_socio: str = ""
    qualificacao_socio: str = ""
    data_entrada_sociedade: str = ""


class BrCnpjResult(BaseModel):
    """Brazil CNPJ business lookup result.

    Source: https://brasilapi.com.br/api/cnpj/v1/{cnpj}
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cnpj: str = ""
    razao_social: str = ""
    nome_fantasia: str = ""
    situacao_cadastral: str = ""
    data_situacao_cadastral: str = ""
    cnae_fiscal: str = ""
    cnae_fiscal_descricao: str = ""
    natureza_juridica: str = ""
    porte: str = ""
    uf: str = ""
    municipio: str = ""
    logradouro: str = ""
    numero: str = ""
    bairro: str = ""
    cep: str = ""
    telefone: str = ""
    email: str = ""
    data_inicio_atividade: str = ""
    socios: list[CnpjSocio] = Field(default_factory=list)
    total_socios: int = 0
    audit: Any | None = Field(default=None, exclude=True)
