"""Nicaragua BCN data model — exchange rates."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NiBcnResult(BaseModel):
    """Nicaragua BCN NIO/USD exchange rate.

    Source: https://www.bcn.gob.ni/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    usd_rate: str = ""
    date: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
