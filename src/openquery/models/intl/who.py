"""WHO Global Health Observatory data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WhoDataPoint(BaseModel):
    """A single country/year/value data point from the WHO GHO OData API."""

    country: str = ""
    year: str = ""
    value: str = ""
    sex: str = ""


class WhoResult(BaseModel):
    """WHO Global Health Observatory indicator query result.

    Source: https://ghoapi.azureedge.net/api/
    Docs: https://www.who.int/data/gho/info/gho-odata-api
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    indicator_code: str = ""
    country_code: str = ""
    total: int = 0
    data_points: list[WhoDataPoint] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
