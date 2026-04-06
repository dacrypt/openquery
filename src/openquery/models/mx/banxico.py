"""Banxico data model — Mexico central bank economic indicators."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BanxicoDataPoint(BaseModel):
    """A single data point in a Banxico time series."""

    date: str = ""
    value: str = ""


class BanxicoResult(BaseModel):
    """Banxico (Banco de México) economic series data.

    Source: https://www.banxico.org.mx/SieAPIRest/service/v1/series/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    series_id: str = ""
    series_name: str = ""
    data_points: list[BanxicoDataPoint] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
