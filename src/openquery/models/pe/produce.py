"""PRODUCE fisheries/industry registration data model — Peru."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProduceResult(BaseModel):
    """PRODUCE industrial/fisheries registration lookup.

    Source: https://www.produce.gob.pe/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    registration_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
