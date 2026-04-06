"""Guatemala OJ data model — judicial cases / jurisprudence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GtOjResult(BaseModel):
    """Guatemala OJ judicial case lookup result.

    Source: https://consultasexternas.oj.gob.gt/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    case_number: str = ""
    court: str = ""
    status: str = ""
    resolution: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
