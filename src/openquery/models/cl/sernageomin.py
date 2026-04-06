"""SERNAGEOMIN mining concessions data model — Chile."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SernageominResult(BaseModel):
    """SERNAGEOMIN mining concession lookup.

    Source: https://www.sernageomin.cl/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    concession_name: str = ""
    holder: str = ""
    status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
