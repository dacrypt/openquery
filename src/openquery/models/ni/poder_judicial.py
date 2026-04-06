"""Nicaragua Poder Judicial data model — NICARAO court cases."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NiPoderJudicialResult(BaseModel):
    """Nicaragua NICARAO court case lookup result.

    Source: https://consultascausas.poderjudicial.gob.ni/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    case_number: str = ""
    court: str = ""
    status: str = ""
    region: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
