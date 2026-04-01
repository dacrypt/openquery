"""Colpensiones data model — Colombian pension affiliation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ColpensionesResult(BaseModel):
    """Colpensiones pension affiliation status.

    Source: https://www.colpensiones.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    nombre: str = ""
    esta_afiliado: bool = False
    estado: str = ""  # "Afiliado activo", "No afiliado", etc.
    regimen: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
