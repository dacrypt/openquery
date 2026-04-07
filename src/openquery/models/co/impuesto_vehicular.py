"""Colombian departmental vehicle tax (impuesto vehicular) data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class VigenciaPendiente(BaseModel):
    """Outstanding tax period."""

    year: str = ""
    value: str = ""
    status: str = ""


class ImpuestoVehicularResult(BaseModel):
    """Result from a Colombian departmental vehicle tax query."""

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    departamento: str = ""
    marca: str = ""
    modelo: str = ""
    cilindraje: str = ""
    tipo_servicio: str = ""
    avaluo: str = ""
    total_deuda: str = ""
    vigencias_pendientes: list[VigenciaPendiente] = Field(default_factory=list)
    estado: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
