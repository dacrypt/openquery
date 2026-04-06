"""PEP Check data model — Politically Exposed Persons check."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PepCheckResult(BaseModel):
    """Politically Exposed Persons (PEP) check result.

    Aggregated across multiple public jurisdictions.
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    is_pep: bool = False
    jurisdictions: list[str] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
