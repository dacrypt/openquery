"""OSCE Sancionados data model — Peruvian sanctioned government suppliers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProveedorSancionado(BaseModel):
    """Single sanctioned supplier record."""

    nombre: str = ""
    ruc: str = ""
    sancion: str = ""
    fecha_inicio: str = ""
    fecha_fin: str = ""
    motivo: str = ""
    estado: str = ""


class OsceSancionadosResult(BaseModel):
    """Sanctioned supplier records from Peru's OSCE.

    Source: https://www.gob.pe/osce
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    total_sancionados: int = 0
    sancionados: list[ProveedorSancionado] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
