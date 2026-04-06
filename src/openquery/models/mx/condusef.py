"""CONDUSEF data model — Mexican financial institution complaints (Buró de Entidades)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CondusefResult(BaseModel):
    """Financial institution complaint data from Mexico's CONDUSEF Buró.

    Source: https://www.buro.gob.mx/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    institution_name: str = ""
    total_complaints: int = 0
    resolution_rate: str = ""  # percentage string e.g. "75.3%"
    products: list[str] = Field(default_factory=list)
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
