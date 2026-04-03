"""Brazil IBGE data model — states and municipalities."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IbgeUF(BaseModel):
    """A Brazilian state."""

    id: int = 0
    sigla: str = ""
    nome: str = ""
    regiao: str = ""


class BrIbgeResult(BaseModel):
    """Brazil IBGE states/municipalities result.

    Source: https://brasilapi.com.br/api/ibge/uf/v1
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    total: int = 0
    estados: list[IbgeUF] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
