"""INPEC data model — Colombian prison population registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InpecResult(BaseModel):
    """INPEC prison population lookup.

    Source: https://www.inpec.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    nombre: str = ""
    esta_recluido: bool = False
    centro_reclusion: str = ""
    situacion_juridica: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
