"""Cambio de Estrato data model — Colombian socioeconomic stratum."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CambioEstratoResult(BaseModel):
    """Socioeconomic stratum certification.

    Source: Various municipal government portals
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    nombre: str = ""
    estrato: str = ""  # "1" through "6"
    direccion: str = ""
    municipio: str = ""
    departamento: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
