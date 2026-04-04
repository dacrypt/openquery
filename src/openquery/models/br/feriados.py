"""Brazil feriados data model — national holidays."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Feriado(BaseModel):
    """A national holiday."""

    date: str = ""
    name: str = ""
    type: str = ""


class BrFeriadosResult(BaseModel):
    """Brazil national holidays result.

    Source: https://brasilapi.com.br/api/feriados/v1/{year}
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    ano: int = 0
    total: int = 0
    feriados: list[Feriado] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
