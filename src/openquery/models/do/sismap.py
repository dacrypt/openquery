"""SISMAP data model — Dominican Republic government transparency."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SismapResult(BaseModel):
    """Dominican Republic SISMAP government performance lookup.

    Source: https://www.sismap.gob.do/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    entity_name: str = ""
    performance_score: str = ""
    evaluation_period: str = ""
    status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
