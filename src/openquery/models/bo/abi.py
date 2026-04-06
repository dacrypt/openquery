"""ABI data model — Bolivia news agency articles."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BoAbiResult(BaseModel):
    """Bolivia ABI news agency search results.

    Source: https://www.abi.bo/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total_results: int = 0
    articles: list[dict] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
