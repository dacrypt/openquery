"""PROCOMER data model — Costa Rica export/trade data."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CrProcomerResult(BaseModel):
    """Costa Rica PROCOMER export statistics.

    Source: https://www.procomer.com/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total_results: int = 0
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
