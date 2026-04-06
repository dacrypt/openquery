"""SEP data model — Mexico professional certification (cédula profesional)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SepResult(BaseModel):
    """Professional license data from Mexico's SEP.

    Source: https://www.cedulaprofesional.sep.gob.mx/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    nombre: str = ""
    cedula_number: str = ""
    institution: str = ""
    degree: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
