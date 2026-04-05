"""Ohio BMV title search data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OhBmvResult(BaseModel):
    """Ohio BMV title search result.

    Source: https://bmvonline.dps.ohio.gov/bmvonline/titles/titlesearch
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    vin: str = ""
    title_number: str = ""
    title_status: str = ""
    lien_status: str = ""
    vehicle_description: str = ""
    owner_verification: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
