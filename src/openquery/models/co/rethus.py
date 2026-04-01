"""RETHUS data model — Colombian health workforce registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RethusResult(BaseModel):
    """RETHUS (Registro Nacional del Talento Humano en Salud) results.

    Source: https://rfrfrethus2.minsalud.gov.co/ReTHUS/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    nombre: str = ""
    esta_registrado: bool = False
    profesion: str = ""
    numero_registro: str = ""
    estado_registro: str = ""
    fecha_registro: str = ""
    universidad: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
