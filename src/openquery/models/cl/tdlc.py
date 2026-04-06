"""TDLC antitrust tribunal data model — Chile."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TdlcResult(BaseModel):
    """TDLC antitrust case lookup.

    Source: https://www.tdlc.cl/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    case_number: str = ""
    status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
