"""Banguat TC data model — Guatemala exchange rates by date."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GtBanguatTcResult(BaseModel):
    """Guatemala Banguat GTQ/USD exchange rate for a specific date.

    Source: https://www.banguat.gob.gt/tipo_cambio/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    date: str = ""
    usd_rate: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
