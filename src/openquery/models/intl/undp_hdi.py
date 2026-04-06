"""UNDP Human Development Index data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UndpHdiResult(BaseModel):
    """UNDP Human Development Index lookup.

    Source: https://hdr.undp.org/data-center/human-development-index
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    country: str = ""
    hdi_score: str = ""
    hdi_rank: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
