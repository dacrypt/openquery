"""TSJ data model — Venezuela Supreme Court case lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TsjResult(BaseModel):
    """Venezuela TSJ Supreme Court case lookup.

    Source: https://www.tsj.gob.ve/en/consulta
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    case_number: str = ""
    chamber: str = ""
    status: str = ""
    ruling: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
