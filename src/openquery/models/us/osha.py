"""OSHA workplace inspections data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OshaViolation(BaseModel):
    """A single OSHA violation record."""

    citation_id: str = ""
    description: str = ""
    penalty: str = ""
    severity: str = ""


class OshaResult(BaseModel):
    """OSHA workplace inspections query result.

    Source: https://enforcedata.dol.gov/views/oshaFilter.php
    Docs: https://enforcedata.dol.gov/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total_inspections: int = 0
    violations: list[OshaViolation] = Field(default_factory=list)
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
