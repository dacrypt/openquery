"""NHTSA Recalls data model — US vehicle safety recalls."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NhtsaRecall(BaseModel):
    """A single NHTSA recall campaign."""

    campaign_number: str = ""
    date_reported: str = ""
    component: str = ""
    summary: str = ""
    consequence: str = ""
    remedy: str = ""
    manufacturer: str = ""
    notes: str = ""


class NhtsaRecallsResult(BaseModel):
    """NHTSA vehicle safety recalls lookup.

    Source: https://api.nhtsa.gov/recalls/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    make: str = ""
    model: str = ""
    model_year: str = ""
    total_recalls: int = 0
    recalls: list[NhtsaRecall] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
