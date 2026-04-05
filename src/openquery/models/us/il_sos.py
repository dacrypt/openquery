"""Illinois SOS title/registration status data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IlSosResult(BaseModel):
    """Illinois Secretary of State title/registration status result.

    Source: https://apps.ilsos.gov/regstatus/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    vin: str = ""
    title_status: str = ""
    registration_status: str = ""
    lien_info: str = ""
    outstanding_fees: str = ""
    vehicle_description: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
