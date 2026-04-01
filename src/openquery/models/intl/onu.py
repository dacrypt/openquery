"""UN Security Council Sanctions data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OnuEntry(BaseModel):
    """A single UN sanctions list entry."""

    reference_number: str = ""
    name: str = ""
    un_list_type: str = ""  # e.g., "Al-Qaida", "Taliban", "ISIL"
    listed_on: str = ""
    comments: str = ""
    nationality: str = ""
    designation: str = ""


class OnuResult(BaseModel):
    """UN Security Council Consolidated Sanctions List screening.

    Source: https://www.un.org/securitycouncil/sanctions/un-sc-consolidated-list
    API: https://scsanctions.un.org/resources/xml/en/consolidated.xml
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    match_count: int = 0
    is_sanctioned: bool = False
    matches: list[OnuEntry] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
