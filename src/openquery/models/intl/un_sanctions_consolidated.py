"""UN Consolidated Sanctions List data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UnSanctionEntry(BaseModel):
    """A single entry from the UN consolidated sanctions list."""

    name: str = ""
    entity_type: str = ""
    list_type: str = ""
    reference_number: str = ""
    nationality: str = ""
    designation: str = ""


class UnSanctionsConsolidatedResult(BaseModel):
    """UN Consolidated Sanctions List search result.

    Source: https://scsanctions.un.org/resources/xml/en/consolidated.xml
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total: int = 0
    entries: list[UnSanctionEntry] = Field(default_factory=list)
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
