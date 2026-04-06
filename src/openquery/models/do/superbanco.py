"""Superintendent of Banks data model — Dominican Republic."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SuperbancoResult(BaseModel):
    """Dominican Republic Superintendent of Banks supervised entity lookup.

    Source: https://sb.gob.do/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    entity_name: str = ""
    entity_type: str = ""
    status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
