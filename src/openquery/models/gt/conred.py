"""CONRED data model — Guatemala disaster/emergency events."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GtConredResult(BaseModel):
    """Guatemala CONRED emergency events search result.

    Source: https://www.conred.gob.gt/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total_events: int = 0
    events: list[dict] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
