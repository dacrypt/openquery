"""ONU Colombia data model — UN sanctions Colombia check."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OnuColombiaResult(BaseModel):
    """UN sanctions Colombia check.

    Source: https://www.cancilleria.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    is_sanctioned: bool = False
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
