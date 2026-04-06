"""ACP Panama Canal Authority data model — Panama."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AutoridadCanalResult(BaseModel):
    """ACP Panama Canal Authority tenders/statistics lookup.

    Source: https://pancanal.com/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total_results: int = 0
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
