"""CNE Partidos data model — Venezuela political party registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class VeCnePartidosResult(BaseModel):
    """Venezuela CNE political party registration status.

    Source: http://www.cne.gob.ve/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    party_name: str = ""
    registration_status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
