"""SUNARP Propiedad data model — Peruvian property registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SunarpPropiedadResult(BaseModel):
    """SUNARP property registry — ownership and liens (Peru).

    Source: https://www.sunarp.gob.pe/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_value: str = ""
    owner: str = ""
    property_type: str = ""
    liens: list[str] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
