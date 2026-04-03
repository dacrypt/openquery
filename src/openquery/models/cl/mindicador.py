"""Chile Mindicador data model — economic indicators."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Indicador(BaseModel):
    """A single economic indicator value."""

    codigo: str = ""
    nombre: str = ""
    unidad: str = ""
    valor: float = 0.0
    fecha: str = ""


class ClMindicadorResult(BaseModel):
    """Chile Mindicador economic indicators result.

    Source: https://mindicador.cl/api
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    uf: float = 0.0
    dolar: float = 0.0
    euro: float = 0.0
    utm: float = 0.0
    ipc: float = 0.0
    total_indicadores: int = 0
    indicadores: list[Indicador] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
