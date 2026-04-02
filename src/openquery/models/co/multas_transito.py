"""Multas de Tránsito local data model — Colombian city-level traffic fines.

Shared model for city-specific transit office sources (Medellín, Bogotá, etc.).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ComparendoLocal(BaseModel):
    """A traffic violation record from a local transit office."""

    numero: str = ""
    tipo: str = ""  # "Comparendo", "Resolución", etc.
    fecha: str = ""
    fecha_notificacion: str = ""
    infraccion: str = ""
    codigo_infraccion: str = ""
    estado: str = ""  # "VIGENTE", "PAGADO", "EN PROCESO"
    placa: str = ""
    saldo: float = 0.0
    interes: float = 0.0
    total: float = 0.0
    medio_imposicion: str = ""


class MultasTransitoLocalResult(BaseModel):
    """Traffic fines from a city-level transit office.

    Used by city-specific sources (co.multas_bogota, co.multas_medellin, etc.).
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    nombre: str = ""
    ciudad: str = ""
    total_comparendos: int = 0
    total_deuda: float = 0.0
    comparendos: list[ComparendoLocal] = Field(default_factory=list)
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
