"""Fiscalizacion data model — Chilean traffic infractions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InfraccionTransito(BaseModel):
    """A single traffic infraction record from Chilean fiscalizacion."""

    fecha: str = ""
    tipo: str = ""
    monto: str = ""
    estado: str = ""
    comuna: str = ""


class FiscalizacionResult(BaseModel):
    """Traffic infraction records from Chile's Registro de Revisores Vehiculares.

    Source: https://rrvv.fiscalizacion.cl/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    patente: str = ""
    infracciones: list[InfraccionTransito] = Field(default_factory=list)
    total_infracciones: int = 0
    audit: Any | None = Field(default=None, exclude=True)
