"""Registro Civil data model — Colombian civil registry certificate."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RegistroCivilResult(BaseModel):
    """Civil registry certificate status.

    Source: https://consultasrc.registraduria.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    nuip: str = ""
    tipo_documento: str = ""
    nombre: str = ""
    fecha_nacimiento: str = ""
    lugar_nacimiento: str = ""
    sexo: str = ""
    estado: str = ""  # "Vigente", "Anulado"
    serial: str = ""
    notaria: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
