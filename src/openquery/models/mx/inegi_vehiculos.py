"""INEGI vehicle registration statistics data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InegiVehiculoDataPoint(BaseModel):
    """A single INEGI vehicle registration data point."""

    period: str = ""
    value: str = ""


class InegiVehiculosResult(BaseModel):
    """INEGI vehicle registration statistics query result.

    Source: https://www.inegi.org.mx/app/api/indicadores/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    indicator: str = ""
    indicator_name: str = ""
    total_observations: int = 0
    data_points: list[InegiVehiculoDataPoint] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
