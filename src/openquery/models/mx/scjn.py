"""SCJN/PJF data model — Mexican federal judicial cases."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MxCaseRecord(BaseModel):
    """Individual case record from SCJN/PJF portal."""

    case_number: str = ""
    court: str = ""
    case_type: str = ""
    status: str = ""
    parties: str = ""
    date: str = ""


class ScjnResult(BaseModel):
    """Federal judicial cases from Mexico's SCJN/PJF portal.

    Source: https://www.serviciosenlinea.pjf.gob.mx/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total: int = 0
    cases: list[MxCaseRecord] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
