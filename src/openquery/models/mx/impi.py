"""IMPI data model — Mexico trademark/patent search."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ImpiResult(BaseModel):
    """IMPI (Instituto Mexicano de la Propiedad Industrial) trademark search result.

    Source: https://marcanet.impi.gob.mx/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    trademark_name: str = ""
    owner: str = ""
    status: str = ""
    registration_date: str = ""
    trademark_class: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
