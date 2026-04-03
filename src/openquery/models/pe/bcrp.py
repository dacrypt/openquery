"""Peru BCRP data model — central bank exchange rates."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BcrpDataPoint(BaseModel):
    """A single exchange rate data point."""

    fecha: str = ""
    valor: str = ""


class PeBcrpResult(BaseModel):
    """Peru BCRP exchange rate result.

    Source: https://estadisticas.bcrp.gob.pe/estadisticas/series/api/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    serie: str = ""
    titulo: str = ""
    ultimo_valor: str = ""
    ultima_fecha: str = ""
    total_datos: int = 0
    datos: list[BcrpDataPoint] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
