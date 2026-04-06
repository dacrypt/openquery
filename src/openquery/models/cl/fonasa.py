"""FONASA data model — Chile health affiliation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FonasaResult(BaseModel):
    """Health affiliation data from Chile's FONASA.

    Source: https://nuevo.fonasa.gob.cl/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    rut: str = ""
    affiliation_status: str = ""
    tier: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
