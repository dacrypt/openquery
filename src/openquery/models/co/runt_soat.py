"""RUNT SOAT data model — Colombian mandatory vehicle insurance."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RuntSoatResult(BaseModel):
    """SOAT (Seguro Obligatorio de Accidentes de Tránsito) status.

    Source: https://www.rfrfrunt.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    tiene_soat: bool = False
    aseguradora: str = ""
    numero_poliza: str = ""
    fecha_inicio: str = ""
    fecha_vencimiento: str = ""
    estado: str = ""  # "Vigente", "Vencido"
    clase_vehiculo: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
