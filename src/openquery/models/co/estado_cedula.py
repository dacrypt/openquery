"""Estado de Cédula data model — Colombian ID card status."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EstadoCedulaResult(BaseModel):
    """Cédula status from Colombia's Registraduría Nacional.

    Source: https://wsp.registraduria.gov.co/certificado/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    fecha_expedicion: str = ""
    estado: str = ""  # "Vigente", "Cancelada por muerte", "No registrada", etc.
    nombre: str = ""
    lugar_expedicion: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
