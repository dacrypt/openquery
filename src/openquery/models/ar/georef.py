"""Argentina GeoRef data model — address normalization and geocoding."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ArGeorefResult(BaseModel):
    """Argentina GeoRef address lookup result.

    Source: https://apis.datos.gob.ar/georef/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    direccion: str = ""
    direccion_normalizada: str = ""
    provincia: str = ""
    departamento: str = ""
    localidad: str = ""
    latitud: float = 0.0
    longitud: float = 0.0
    total_resultados: int = 0
    audit: Any | None = Field(default=None, exclude=True)
