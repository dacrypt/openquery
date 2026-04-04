"""Brazil NCM data model — product classification for trade/customs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NcmItem(BaseModel):
    """An NCM product classification item."""

    codigo: str = ""
    descricao: str = ""
    data_inicio: str = ""
    data_fim: str = ""


class BrNcmResult(BaseModel):
    """Brazil NCM product classification result.

    Source: https://brasilapi.com.br/api/ncm/v1
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    total: int = 0
    itens: list[NcmItem] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
