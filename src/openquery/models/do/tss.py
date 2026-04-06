"""Dominican Republic TSS social security affiliation model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TssResult(BaseModel):
    """TSS social security affiliation result for Dominican Republic.

    Source: https://www.tss.gob.do/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    affiliation_status: str = ""
    employer: str = ""
    ars: str = ""  # Administradora de Riesgos de Salud
    afp: str = ""  # Administradora de Fondos de Pensiones
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
