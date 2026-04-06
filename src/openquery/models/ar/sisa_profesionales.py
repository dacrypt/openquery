"""SISA Profesionales data model — Argentine health professionals registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SisaProfesionalesResult(BaseModel):
    """SISA health professionals registration (Argentina).

    Source: https://sisa.msal.gov.ar/sisa/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    nombre: str = ""
    profession: str = ""
    registration_status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
