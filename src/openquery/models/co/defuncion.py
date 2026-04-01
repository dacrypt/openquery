"""Defunción / Vigencia de Cédula data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DefuncionResult(BaseModel):
    """Cédula vigencia (alive/deceased) from Registraduría.

    Source: https://consultasrc.registraduria.gov.co/ProyectoSCCRC/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    estado: str = ""  # "Vigente", "Cancelada por muerte", "No registrada"
    nombre: str = ""
    esta_vivo: bool = True
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
