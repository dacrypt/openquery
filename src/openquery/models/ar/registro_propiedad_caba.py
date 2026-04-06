"""Registro Propiedad CABA data model — Buenos Aires property registry (Argentina)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RegistroPropiedadCabaResult(BaseModel):
    """CABA property registry — ownership data (Argentina).

    Source: https://www.buenosaires.gob.ar/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_value: str = ""
    owner: str = ""
    property_type: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
