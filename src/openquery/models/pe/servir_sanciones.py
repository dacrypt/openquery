"""SERVIR Sanciones data model — Peruvian public servant sanctions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SancionServidor(BaseModel):
    """Single public servant sanction record."""

    nombre: str = ""
    entidad: str = ""
    tipo_sancion: str = ""
    fecha: str = ""
    duracion: str = ""
    estado: str = ""


class ServirSancionesResult(BaseModel):
    """Public servant sanction records from Peru's SERVIR.

    Source: https://sanciones.gob.pe/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    total_sanciones: int = 0
    sanciones: list[SancionServidor] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
