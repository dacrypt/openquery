"""World Bank country indicators data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorldBankDataPoint(BaseModel):
    """A single year/value data point from the World Bank API."""

    year: str = ""
    value: str = ""


class WorldBankResult(BaseModel):
    """World Bank country indicator query result.

    Source: https://api.worldbank.org/v2/
    Docs: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    country_code: str = ""
    country_name: str = ""
    indicator_code: str = ""
    indicator_name: str = ""
    data_points: list[WorldBankDataPoint] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
