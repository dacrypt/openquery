"""Panama Organo Judicial data model — court case search."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PaProcesoRecord(BaseModel):
    """A single court process/case record."""

    case_number: str = ""
    court: str = ""
    case_type: str = ""
    status: str = ""
    filing_date: str = ""
    parties: str = ""


class OrganoJudicialResult(BaseModel):
    """Panama Organo Judicial court case search result.

    Source: https://ojpanama.organojudicial.gob.pa/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_value: str = ""
    total: int = 0
    processes: list[PaProcesoRecord] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
