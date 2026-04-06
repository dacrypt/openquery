"""Honduras CNBS banking supervisor model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HnCnbsResult(BaseModel):
    """Honduras CNBS supervised entity result.

    Source: https://www.cnbs.gob.hn/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    entity_name: str = ""
    entity_type: str = ""
    status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
