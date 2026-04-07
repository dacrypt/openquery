"""Salud data model — Puerto Rico Department of Health facility lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PrSaludResult(BaseModel):
    """Puerto Rico Department of Health facility lookup.

    Source: https://www.salud.pr.gov/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    facility_name: str = ""
    facility_type: str = ""
    license_number: str = ""
    license_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
