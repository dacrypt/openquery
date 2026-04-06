"""DANE data model — Colombian statistics API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DaneResult(BaseModel):
    """DANE statistics API result.

    Source: https://www.dane.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    indicator: str = ""
    value: str = ""
    period: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
