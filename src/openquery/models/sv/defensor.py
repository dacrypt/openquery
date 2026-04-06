"""Defensor data model — El Salvador consumer complaints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SvDefensorResult(BaseModel):
    """El Salvador Defensoría del Consumidor complaints result.

    Source: https://www.defensoria.gob.sv/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    total_complaints: int = 0
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
