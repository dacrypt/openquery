"""COPNIA data model — Colombian engineering professional council."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CopniaResult(BaseModel):
    """COPNIA (Consejo Profesional Nacional de Ingeniería) lookup.

    Source: https://www.copnia.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    nombre: str = ""
    esta_registrado: bool = False
    matricula: str = ""
    estado_matricula: str = ""  # "Vigente", "Suspendida", "Cancelada"
    profesion: str = ""
    fecha_registro: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
