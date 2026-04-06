"""SUGEF data model — Costa Rica supervised financial entities."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SugefResult(BaseModel):
    """Costa Rica SUGEF supervised financial entities lookup.

    Source: https://www.sugef.fi.cr/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    entity_name: str = ""
    entity_type: str = ""
    supervision_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
