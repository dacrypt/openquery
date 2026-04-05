"""Panama Tribunal Electoral data model — identity verification."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TribunalElectoralResult(BaseModel):
    """Panama Tribunal Electoral identity lookup result.

    Source: https://verificate.te.gob.pa/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    nombre: str = ""
    estado: str = ""
    circuito: str = ""
    corregimiento: str = ""
    centro_votacion: str = ""
    mesa: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
