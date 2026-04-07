"""EPM EV charging stations data model — Colombia public EV/CNG stations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EpmStation(BaseModel):
    """An EV/CNG charging station from EPM (Colombia)."""

    nombre: str = ""
    direccion: str = ""
    ciudad: str = ""
    departamento: str = ""
    tipo: str = ""
    latitud: float = 0.0
    longitud: float = 0.0


class EstacionesEvEpmResult(BaseModel):
    """EPM EV charging stations search result.

    Source: https://www.datos.gov.co/resource/qqm3-dw2u.json
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_params: str = ""
    total_stations: int = 0
    stations: list[EpmStation] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
