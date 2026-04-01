"""SIEM data model — Mexican business registry (Secretaria de Economia)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EmpresaSiem(BaseModel):
    """A single business entry from Mexico's SIEM registry."""

    nombre: str = ""
    rfc: str = ""
    direccion: str = ""
    municipio: str = ""
    estado: str = ""
    actividad: str = ""
    tamano: str = ""  # "Micro", "Pequena", "Mediana", "Grande"
    telefono: str = ""


class SiemResult(BaseModel):
    """Business registry lookup from Mexico's SIEM (Secretaria de Economia).

    Source: https://siem.economia.gob.mx/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    consulta: str = ""  # nombre, rfc, or actividad queried
    empresas: list[EmpresaSiem] = Field(default_factory=list)
    total_empresas: int = 0
    audit: Any | None = Field(default=None, exclude=True)
