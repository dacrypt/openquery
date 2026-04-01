"""Licencias de Salud data model — Colombian health facility licenses."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LicenciaSalud(BaseModel):
    """A health facility license record."""

    prestador: str = ""
    nit: str = ""
    nombre: str = ""
    clase: str = ""
    naturaleza: str = ""
    departamento: str = ""
    municipio: str = ""
    direccion: str = ""
    telefono: str = ""
    estado: str = ""
    nivel: str = ""


class LicenciasSaludResult(BaseModel):
    """REPS (Registro Especial de Prestadores de Servicios de Salud) lookup.

    Source: https://www.datos.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    total: int = 0
    prestadores: list[LicenciaSalud] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
