"""Lista Clinton data model — Colombia SDN/OFAC sanctions list check."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ListaClintonResult(BaseModel):
    """Colombia Clinton List (SDN/OFAC) sanctions check.

    Source: https://www.datos.gov.co/ / OFAC cross-reference
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    is_listed: bool = False
    list_type: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
