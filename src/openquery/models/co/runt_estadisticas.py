"""RUNT fleet statistics data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RuntEstadistica(BaseModel):
    """A single fleet statistic record."""

    marca: str = ""
    clase: str = ""
    servicio: str = ""
    combustible: str = ""
    departamento: str = ""
    cantidad: int = 0


class RuntEstadisticasResult(BaseModel):
    """RUNT fleet statistics query result.

    Source: https://www.datos.gov.co/resource/u3vn-bdcy.json
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total_records: int = 0
    total_vehiculos: int = 0
    estadisticas: list[RuntEstadistica] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
