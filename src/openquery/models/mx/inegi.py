"""Mexico INEGI data model — geostatistical catalog."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InegiEntidad(BaseModel):
    """A Mexican state/entity from INEGI."""

    clave: str = ""
    nombre: str = ""
    poblacion_total: int = 0
    poblacion_masculina: int = 0
    poblacion_femenina: int = 0
    viviendas: int = 0


class MxInegiResult(BaseModel):
    """Mexico INEGI geostatistical catalog result.

    Source: https://gaia.inegi.org.mx/wscatgeo/v2/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    nivel: str = ""
    total: int = 0
    entidades: list[InegiEntidad] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
