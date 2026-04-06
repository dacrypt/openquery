"""Honduras IHSS social security model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HnIhssResult(BaseModel):
    """Honduras IHSS social security affiliation result.

    Source: https://www.ihss.hn/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    identidad: str = ""
    affiliation_status: str = ""
    employer: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
