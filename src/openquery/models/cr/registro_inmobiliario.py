"""Costa Rica property registry (Registro Inmobiliario) model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RegistroInmobiliarioResult(BaseModel):
    """Property registry result for Costa Rica.

    Source: https://www.rnpdigital.com/registro_inmobiliario/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    finca_number: str = ""
    owner: str = ""
    liens: str = ""
    property_type: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
