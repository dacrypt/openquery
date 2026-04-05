"""NICB VINCheck data model — stolen/salvage vehicle check."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NicbVincheckResult(BaseModel):
    """NICB VINCheck result.

    Source: https://www.nicb.org/vincheck
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    vin: str = ""
    theft_records_found: bool = False
    salvage_records_found: bool = False
    status_message: str = ""
    details: list[str] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
