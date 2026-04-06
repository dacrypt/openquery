"""Global Terrorism Database data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GlobalTerrorismResult(BaseModel):
    """Global Terrorism Database (GTD) result.

    Source: https://www.start.umd.edu/gtd/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total_incidents: int = 0
    incidents: list[dict] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
