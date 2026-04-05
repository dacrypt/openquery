"""Colorado stolen vehicle check data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CoStolenResult(BaseModel):
    """Colorado stolen vehicle check result.

    Source: https://secure.colorado.gov/apps/dps/mvvs/public/entry.jsf
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    vin: str = ""
    model_year: str = ""
    is_stolen: bool = False
    status_message: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
