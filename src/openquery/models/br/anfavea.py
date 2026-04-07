"""ANFAVEA vehicle production/sales data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AnfaveaSegment(BaseModel):
    """Production/sales data for a vehicle segment."""

    segment: str = ""  # automobiles, light commercial, trucks, buses
    production: int = 0
    licensing: int = 0
    exports: int = 0


class AnfaveaResult(BaseModel):
    """ANFAVEA vehicle production/sales query result.

    Source: https://anfavea.com.br/site/edicoes-em-excel/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    period: str = ""
    total_production: int = 0
    total_licensing: int = 0
    total_exports: int = 0
    segments: list[AnfaveaSegment] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
