"""Panama MINSA data model — health registry lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MinsaResult(BaseModel):
    """MINSA health registry lookup result.

    Source: https://www.minsa.gob.pa/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    establishment_name: str = ""
    permit_status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
