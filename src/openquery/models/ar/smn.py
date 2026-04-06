"""SMN weather/climate data model — Argentina."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SmnResult(BaseModel):
    """SMN (Servicio Meteorológico Nacional) weather data lookup.

    Source: https://www.smn.gob.ar/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    city: str = ""
    temperature: str = ""
    conditions: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
