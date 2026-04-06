"""ONPE data model — Peru electoral processes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OnpeResult(BaseModel):
    """Electoral participation data from Peru's ONPE.

    Source: https://www.onpe.gob.pe/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    dni: str = ""
    nombre: str = ""
    electoral_location: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
