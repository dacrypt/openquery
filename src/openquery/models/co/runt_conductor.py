"""RUNT Conductor data model — Colombian driver information."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LicenciaConduccion(BaseModel):
    """A driving license record."""

    categoria: str = ""
    fecha_expedicion: str = ""
    fecha_vencimiento: str = ""
    estado: str = ""
    organismo_transito: str = ""


class RuntConductorResult(BaseModel):
    """RUNT driver information (complements RUNT vehicle data).

    Source: https://www.rfrfrunt.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    nombre: str = ""
    tiene_licencia: bool = False
    licencias: list[LicenciaConduccion] = Field(default_factory=list)
    total_comparendos: int = 0
    tiene_restricciones: bool = False
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
