"""INAMU data model — Costa Rica women's rights/gender violence registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InamuResult(BaseModel):
    """Costa Rica INAMU registry lookup.

    Source: https://www.inamu.go.cr/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    found: bool = False
    registry_type: str = ""
    status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
