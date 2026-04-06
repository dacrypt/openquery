"""Registro Propiedad data model — Paraguayan property registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RegistroPropiedadPyResult(BaseModel):
    """Paraguay property registry — finca-based ownership data.

    Source: https://www.pj.gov.py/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    finca_number: str = ""
    owner: str = ""
    property_type: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
