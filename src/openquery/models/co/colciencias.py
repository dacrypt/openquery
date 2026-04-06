"""MinCiencias/Colciencias research groups data model — Colombia."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ColcienciasResult(BaseModel):
    """MinCiencias research groups/researchers lookup.

    Source: https://scienti.minciencias.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    researcher_name: str = ""
    group: str = ""
    category: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
