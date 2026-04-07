"""CarQuery vehicle specs data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UsCarQueryResult(BaseModel):
    """CarQuery vehicle trim specs result.

    Source: https://www.carqueryapi.com/api/0.3/
    """

    make: str = ""
    model: str = ""
    year: str = ""
    trim: str = ""
    body_style: str = ""
    engine: str = ""
    fuel_type: str = ""
    doors: str = ""
    seats: str = ""
    details: str = ""
    trims: list[dict] = Field(default_factory=list)
    queried_at: datetime = Field(default_factory=datetime.now)
    audit: Any | None = Field(default=None, exclude=True)
