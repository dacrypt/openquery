"""Brazil DDD data model — area code lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BrDddResult(BaseModel):
    """Brazil DDD area code lookup result.

    Source: https://brasilapi.com.br/api/ddd/v1/{ddd}
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    ddd: str = ""
    state: str = ""
    cities: list[str] = Field(default_factory=list)
    total_cities: int = 0
    audit: Any | None = Field(default=None, exclude=True)
