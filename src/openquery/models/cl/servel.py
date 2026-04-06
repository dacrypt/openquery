"""Servel data model — Chile electoral service."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ServelResult(BaseModel):
    """Electoral information from Chile's Servel.

    Source: https://www.servel.cl/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    rut: str = ""
    nombre: str = ""
    voting_location: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
