"""Honduras Poder Judicial data model — SEJE court cases."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HnPoderJudicialResult(BaseModel):
    """Honduras Poder Judicial SEJE court case lookup result.

    Source: https://sejeinfo.poderjudicial.gob.hn/sejeinfo/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    case_number: str = ""
    court: str = ""
    status: str = ""
    proceedings: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
