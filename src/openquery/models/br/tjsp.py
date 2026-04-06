"""Brazil TJSP data model — São Paulo court cases lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TjspResult(BaseModel):
    """TJSP São Paulo court case lookup result.

    Source: https://esaj.tjsp.jus.br/cjpg/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total_cases: int = 0
    cases: list[dict[str, str]] = Field(default_factory=list)
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
