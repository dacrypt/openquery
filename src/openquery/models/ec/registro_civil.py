"""Registro Civil data model — Ecuador civil registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RegistroCivilEcResult(BaseModel):
    """Identity and civil status data from Ecuador's Registro Civil.

    Source: https://www.registrocivil.gob.ec/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    nombre: str = ""
    civil_status: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
