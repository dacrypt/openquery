"""SAM.gov Exclusions data model — US debarment/excluded parties."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SamExclusion(BaseModel):
    """A single SAM.gov excluded party record."""

    name: str = ""
    entity_type: str = ""
    exclusion_type: str = ""
    agency: str = ""
    date: str = ""


class SamExclusionsResult(BaseModel):
    """SAM.gov excluded parties (debarment) search result.

    Source: https://api.sam.gov/entity-information/v3/exclusions
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total: int = 0
    exclusions: list[SamExclusion] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
