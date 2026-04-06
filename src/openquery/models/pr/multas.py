"""Puerto Rico DTOP traffic fines model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MultasResult(BaseModel):
    """Data from Puerto Rico DTOP traffic fines system.

    Source: https://dtop.pr.gov/
    """

    search_value: str = ""
    total_fines: int = 0
    fines_amount: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
