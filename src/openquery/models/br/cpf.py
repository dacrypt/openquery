"""Brazil CPF data model — Receita Federal citizen identity."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BrCpfResult(BaseModel):
    """Brazil CPF lookup result.

    Source: https://servicos.receita.fazenda.gov.br/servicos/cpf/consultasituacao/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cpf: str = ""
    nome: str = ""
    situacao_cadastral: str = ""
    data_inscricao: str = ""
    digito_verificador: str = ""
    comprovante: str = ""
    audit: Any | None = Field(default=None, exclude=True)
