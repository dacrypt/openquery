"""Guatemala Banguat data model — exchange rates."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TipoCambio(BaseModel):
    """A daily exchange rate entry."""

    fecha: str = ""
    referencia: str = ""


class GtBanguatResult(BaseModel):
    """Guatemala Banguat exchange rate result.

    Source: https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    moneda: str = "USD/GTQ"
    tipo_cambio: str = ""
    fecha: str = ""
    total_registros: int = 0
    registros: list[TipoCambio] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
