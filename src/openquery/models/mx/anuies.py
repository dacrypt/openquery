"""ANUIES university data model — Mexico."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AnuiesResult(BaseModel):
    """ANUIES university registry lookup.

    Source: https://www.anuies.mx/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    institution_name: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
