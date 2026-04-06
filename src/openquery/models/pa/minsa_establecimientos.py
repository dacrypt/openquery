"""MINSA Establecimientos data model — Panamanian health providers registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MinsaEstablecimientosResult(BaseModel):
    """MINSA health providers and licenses registry (Panama).

    Source: https://www.minsa.gob.pa/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    provider_name: str = ""
    license_status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
