"""Trabajo data model — Puerto Rico Department of Labor employer lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PrTrabajoResult(BaseModel):
    """Puerto Rico Department of Labor employer compliance lookup.

    Source: https://www.trabajo.pr.gov/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    employer_name: str = ""
    compliance_status: str = ""
    industry: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
