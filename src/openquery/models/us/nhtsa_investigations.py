"""NHTSA Investigations data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NhtsaInvestigation(BaseModel):
    """Individual NHTSA defect investigation."""

    nhtsa_id: str = ""
    investigation_number: str = ""
    investigation_type: str = ""
    subject: str = ""
    description: str = ""
    status: str = ""
    open_date: str = ""
    close_date: str = ""
    components: list[str] = Field(default_factory=list)
    make: str = ""
    model: str = ""
    year: str = ""


class NhtsaInvestigationsResult(BaseModel):
    """NHTSA ODI defect investigations result.

    Source: https://api.nhtsa.gov/investigations
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    make: str = ""
    model: str = ""
    model_year: str = ""
    total: int = 0
    investigations: list[NhtsaInvestigation] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
