"""Uruguay MSP health facility registry model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UyMspResult(BaseModel):
    """Data from Uruguay MSP health facility registry.

    Source: https://www.gub.uy/ministerio-salud-publica/
    """

    search_term: str = ""
    facility_name: str = ""
    permit_status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
