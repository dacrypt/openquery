"""EPA TRIS data model — US Toxics Release Inventory."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EpaTrisResult(BaseModel):
    """EPA Toxics Release Inventory (TRI) result.

    Source: https://enviro.epa.gov/enviro/efservice/TRI_FACILITY/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total_facilities: int = 0
    facilities: list[dict] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
