"""SMA data model — Chile environmental sanctions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SmaResult(BaseModel):
    """Environmental sanctions data from Chile's SMA.

    Source: https://snifa.sma.gob.cl/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    total_sanctions: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
