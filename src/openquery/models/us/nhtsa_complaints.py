"""NHTSA Complaints data model — US vehicle safety complaints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NhtsaComplaint(BaseModel):
    """A single NHTSA consumer complaint."""

    odi_number: str = ""
    date_complaint: str = ""
    component: str = ""
    summary: str = ""
    crash: bool = False
    fire: bool = False
    injuries: int = 0
    deaths: int = 0


class NhtsaComplaintsResult(BaseModel):
    """NHTSA vehicle safety complaints lookup.

    Source: https://api.nhtsa.gov/complaints/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    make: str = ""
    model: str = ""
    model_year: str = ""
    total_complaints: int = 0
    complaints: list[NhtsaComplaint] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
