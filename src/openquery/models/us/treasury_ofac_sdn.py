"""Treasury OFAC SDN data model — US sanctions detailed list."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SdnEntry(BaseModel):
    """A single SDN (Specially Designated National) list entry."""

    uid: str = ""
    name: str = ""
    sdn_type: str = ""
    programs: list[str] = Field(default_factory=list)
    remarks: str = ""


class TreasuryOfacSdnResult(BaseModel):
    """Treasury OFAC SDN list detailed result.

    Source: https://www.treasury.gov/ofac/downloads/sdn.xml
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total: int = 0
    sdn_entries: list[SdnEntry] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
