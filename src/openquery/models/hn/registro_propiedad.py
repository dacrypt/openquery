"""Registro Propiedad data model — Honduras property registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HnRegistroPropiedadResult(BaseModel):
    """Honduras property registry lookup.

    Source: https://www.ip.gob.hn/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    property_number: str = ""
    owner_name: str = ""
    property_type: str = ""
    location: str = ""
    registration_date: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
