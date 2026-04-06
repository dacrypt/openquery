"""Puerto Rico OCIF banking supervisor model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PrOcifResult(BaseModel):
    """Data from Puerto Rico OCIF supervised financial institutions.

    Source: https://www.ocif.gobierno.pr/
    """

    search_term: str = ""
    entity_name: str = ""
    entity_type: str = ""
    status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
