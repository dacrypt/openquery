"""DNRPA vehicle registration statistics data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DnrpaEstadistica(BaseModel):
    """A single DNRPA registration statistic record."""

    year: str = ""
    month: str = ""
    province: str = ""
    tramite_type: str = ""
    quantity: int = 0


class DnrpaEstadisticasResult(BaseModel):
    """DNRPA vehicle registration statistics query result.

    Source: https://datos.gob.ar/dataset/justicia-estadistica-tramites-automotores
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total_records: int = 0
    estadisticas: list[DnrpaEstadistica] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
