"""World Development Indicators data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WdiDataPoint(BaseModel):
    """A single year/value data point from the WDI API."""

    year: str = ""
    value: str = ""


class WdiResult(BaseModel):
    """World Development Indicators query result.

    Source: https://databank.worldbank.org/
    Docs: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    country_code: str = ""
    indicator: str = ""
    data_points: list[WdiDataPoint] = Field(default_factory=list)
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
