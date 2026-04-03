"""Argentina economic series data model — datos.gob.ar time series."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ArSeriesResult(BaseModel):
    """Argentina economic time series result.

    Source: https://apis.datos.gob.ar/series/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    serie_id: str = ""
    serie_titulo: str = ""
    serie_unidades: str = ""
    serie_fuente: str = ""
    frecuencia: str = ""
    ultimo_valor: float = 0.0
    ultima_fecha: str = ""
    total_datos: int = 0
    datos: list[list] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
