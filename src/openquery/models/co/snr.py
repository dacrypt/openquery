"""SNR data model — Colombian property registry (SuperNotariado)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SnrPropiedad(BaseModel):
    """A property record from SNR."""

    matricula_inmobiliaria: str = ""
    tipo: str = ""  # "Urbano", "Rural"
    departamento: str = ""
    municipio: str = ""
    direccion: str = ""
    estado: str = ""


class SnrResult(BaseModel):
    """SNR (Superintendencia de Notariado y Registro) results.

    Source: https://radicacion.supernotariado.gov.co/app/consultaradicacion.html
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    nombre: str = ""
    tiene_propiedades: bool = False
    total_propiedades: int = 0
    propiedades: list[SnrPropiedad] = Field(default_factory=list)
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
