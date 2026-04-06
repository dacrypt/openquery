"""FCC broadband availability data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FccProvider(BaseModel):
    """A single broadband provider at a location."""

    name: str = ""
    technology: str = ""
    speed: str = ""


class FccBroadbandResult(BaseModel):
    """FCC broadband availability query result.

    Source: https://broadbandmap.fcc.gov/api/
    Docs: https://broadbandmap.fcc.gov/about
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    location: str = ""
    providers: list[FccProvider] = Field(default_factory=list)
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
