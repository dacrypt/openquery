"""OEFA environmental enforcement data model — Peru."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OefaResult(BaseModel):
    """OEFA environmental sanctions lookup.

    Source: https://www.oefa.gob.pe/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    total_sanctions: int = 0
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
