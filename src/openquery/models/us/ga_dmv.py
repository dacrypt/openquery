"""Georgia DRIVES vehicle status data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GaDmvResult(BaseModel):
    """Georgia DRIVES vehicle title and insurance status result.

    Source: https://eservices.drives.ga.gov/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_type: str = ""  # "title" or "insurance"
    search_value: str = ""
    title_status: str = ""
    lienholder: str = ""
    brand_info: str = ""
    insurance_status: str = ""
    vehicle_description: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
