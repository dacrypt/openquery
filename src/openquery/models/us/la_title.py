"""Louisiana OMV title verification data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LaTitleResult(BaseModel):
    """Louisiana OMV title verification result.

    Source: https://la.accessgov.com/title-verification/Forms/Page/title-verification/check
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_value: str = ""
    search_type: str = ""  # "vin" or "title_number"
    title_valid: bool = False
    status_message: str = ""
    vehicle_description: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
