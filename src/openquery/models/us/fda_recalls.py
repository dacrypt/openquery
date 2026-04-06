"""FDA Recalls data model — US food/drug recall events."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FdaRecallEvent(BaseModel):
    """A single FDA recall event."""

    product: str = ""
    company: str = ""
    reason: str = ""
    classification: str = ""
    status: str = ""
    date: str = ""


class FdaRecallsResult(BaseModel):
    """FDA food/drug enforcement recall search result.

    Source: https://api.fda.gov/drug/enforcement.json
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total: int = 0
    recalls: list[FdaRecallEvent] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
