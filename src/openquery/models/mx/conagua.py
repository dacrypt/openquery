"""CONAGUA water concessions data model — Mexico."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConaguaResult(BaseModel):
    """CONAGUA water concession lookup.

    Source: https://www.gob.mx/conagua
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    concession_name: str = ""
    holder: str = ""
    status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
