"""US Census Bureau data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CensusResult(BaseModel):
    """US Census Bureau ACS data query result.

    Source: https://api.census.gov/data/
    Docs: https://www.census.gov/data/developers/guidance/api-user-guide.html
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    geography: str = ""
    variable: str = ""
    value: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
