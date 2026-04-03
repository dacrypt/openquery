"""Brazil CVM corretoras data model — stock broker registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BrCorretoraResult(BaseModel):
    """Brazil CVM stock broker lookup result.

    Source: https://brasilapi.com.br/api/cvm/corretoras/v1/{cnpj}
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cnpj: str = ""
    nome_social: str = ""
    nome_comercial: str = ""
    status: str = ""
    email: str = ""
    telefone: str = ""
    municipio: str = ""
    uf: str = ""
    codigo_cvm: str = ""
    valor_patrimonio_liquido: str = ""
    audit: Any | None = Field(default=None, exclude=True)
