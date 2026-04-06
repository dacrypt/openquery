"""EU Consolidated Sanctions List data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EuSanctionEntry(BaseModel):
    """A single entry from the EU consolidated sanctions list."""

    name: str = ""
    entity_type: str = ""
    program: str = ""
    listed_date: str = ""
    details: str = ""


class EuSanctionsResult(BaseModel):
    """EU Consolidated Sanctions List screening result.

    Source: https://webgate.ec.europa.eu/fsd/fsf/
    XML: https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total: int = 0
    entries: list[EuSanctionEntry] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
