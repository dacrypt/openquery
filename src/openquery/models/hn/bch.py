"""BCH data model — Honduras Central Bank exchange rates."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HnBchResult(BaseModel):
    """Honduras BCH HNL/USD exchange rate.

    Source: https://www.bch.hn/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    usd_rate: str = ""
    date: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
