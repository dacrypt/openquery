"""Brazil CEP data model — zip code lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BrCepResult(BaseModel):
    """Brazil CEP (zip code) lookup result.

    Source: https://brasilapi.com.br/api/cep/v2/{cep}
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cep: str = ""
    estado: str = ""
    cidade: str = ""
    bairro: str = ""
    logradouro: str = ""
    complemento: str = ""
    ibge: str = ""
    ddd: str = ""
    audit: Any | None = Field(default=None, exclude=True)
