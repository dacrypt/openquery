"""Estado data model — Puerto Rico Department of State business filings."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PrEstadoResult(BaseModel):
    """Puerto Rico Department of State business filing lookup.

    Source: https://prcorpfiling.f1hst.com/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    entity_name: str = ""
    entity_type: str = ""
    registration_number: str = ""
    status: str = ""
    registration_date: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
