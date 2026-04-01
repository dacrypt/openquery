"""OFAC SDN List data model — US Treasury sanctions screening."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OfacEntry(BaseModel):
    """A single OFAC SDN match."""

    uid: str = ""
    name: str = ""
    type: str = ""  # "Individual" or "Entity"
    programs: list[str] = Field(default_factory=list)
    remarks: str = ""
    score: float = 0.0  # match score if fuzzy


class OfacResult(BaseModel):
    """OFAC SDN List screening results.

    Source: https://sanctionssearch.ofac.treas.gov/
    API: https://sanctionssearch.ofac.treas.gov/Details.aspx
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    match_count: int = 0
    is_sanctioned: bool = False
    matches: list[OfacEntry] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
