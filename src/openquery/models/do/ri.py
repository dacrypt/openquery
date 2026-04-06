"""Dominican Republic Registro Inmobiliario property registry model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RiResult(BaseModel):
    """Property registry result for Dominican Republic.

    Source: https://servicios.ri.gob.do/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_value: str = ""
    property_status: str = ""
    owner: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
