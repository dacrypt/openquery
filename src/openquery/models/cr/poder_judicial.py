"""Costa Rica Poder Judicial court cases data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CrPoderJudicialResult(BaseModel):
    """Costa Rica Poder Judicial court case lookup result.

    Source: https://pj.poder-judicial.go.cr/index.php/consultas-en-linea
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_value: str = ""
    case_number: str = ""
    court: str = ""
    status: str = ""
    parties: str = ""
    filing_date: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
