"""Comparendos de Tránsito data model — Colombian traffic violations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Comparendo(BaseModel):
    """A traffic violation record."""

    numero: str = ""
    fecha: str = ""
    infraccion: str = ""
    codigo_infraccion: str = ""
    valor: str = ""
    estado: str = ""  # "Pendiente", "Pagado", "En proceso"
    secretaria_transito: str = ""
    placa: str = ""


class ComparendosTransitoResult(BaseModel):
    """Traffic violations (comparendos) from SIMIT/transit authorities.

    Source: https://www.fcm.org.co/simit/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    nombre: str = ""
    total_comparendos: int = 0
    total_deuda: float = 0.0
    comparendos: list[Comparendo] = Field(default_factory=list)
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
