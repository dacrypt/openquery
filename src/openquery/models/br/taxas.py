"""Brazil taxas data model — interest rates."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Taxa(BaseModel):
    """An interest rate."""

    nome: str = ""
    valor: float = 0.0


class BrTaxasResult(BaseModel):
    """Brazil interest rates result.

    Source: https://brasilapi.com.br/api/taxas/v1
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    selic: float = 0.0
    cdi: float = 0.0
    ipca: float = 0.0
    total: int = 0
    taxas: list[Taxa] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
