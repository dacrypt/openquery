"""ECLAC/CEPAL statistics data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EclacDataPoint(BaseModel):
    """A single observation from the ECLAC/CEPAL statistics portal."""

    period: str = ""
    value: str = ""


class EclacResult(BaseModel):
    """ECLAC/CEPAL Latin America statistics query result.

    Source: https://statistics.cepal.org/portal/cepalstat/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    indicator: str = ""
    country_code: str = ""
    data_points: list[EclacDataPoint] = Field(default_factory=list)
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
