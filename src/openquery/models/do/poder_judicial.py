"""Poder Judicial data model — Dominican Republic court cases."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DoPodeJudicialResult(BaseModel):
    """Dominican Republic Poder Judicial court case lookup.

    Source: https://www.poderjudicial.gob.do/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    case_number: str = ""
    court: str = ""
    status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
