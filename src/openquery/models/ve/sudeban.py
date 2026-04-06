"""SUDEBAN data model — Venezuela banking supervisor."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SudebanResult(BaseModel):
    """SUDEBAN (Superintendencia de las Instituciones del Sector Bancario) result.

    Source: https://www.sudeban.gob.ve/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    entity_name: str = ""
    entity_type: str = ""
    status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
