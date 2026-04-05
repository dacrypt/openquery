"""New York DMV title/lien status data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NyDmvResult(BaseModel):
    """New York DMV title/lien status result.

    Source: https://process.dmv.ny.gov/titlestatus/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    vin: str = ""
    make: str = ""
    model_year: str = ""
    title_status: str = ""
    lien_status: str = ""
    vehicle_description: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
