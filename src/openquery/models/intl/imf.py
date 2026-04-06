"""IMF DataMapper economic indicators data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ImfDataPoint(BaseModel):
    """A single year/value data point from the IMF DataMapper API."""

    year: str = ""
    value: str = ""


class ImfResult(BaseModel):
    """IMF DataMapper indicator query result.

    Source: https://www.imf.org/external/datamapper/api/v1/
    Docs: https://www.imf.org/external/datamapper/api/help
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    country_code: str = ""
    indicator_code: str = ""
    indicator_name: str = ""
    data_points: list[ImfDataPoint] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
