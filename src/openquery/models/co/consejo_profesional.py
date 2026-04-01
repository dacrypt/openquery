"""Consejo Profesional data model — Generic model for all professional councils."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConsejoProfesionalResult(BaseModel):
    """Generic professional council license/registration lookup.

    Used by: COPNIA, CONALTEL, CPAE, CPIP, CPIQ, CPNAA, CPNT,
    CPBiol, Consejo Mecánica/Electrónica, Veterinario, URNA.
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    tipo_documento: str = ""
    nombre: str = ""
    consejo: str = ""  # Name of the professional council
    esta_registrado: bool = False
    matricula: str = ""
    estado_matricula: str = ""  # "Vigente", "Suspendida", "Cancelada", etc.
    profesion: str = ""
    especialidad: str = ""
    fecha_registro: str = ""
    fecha_vencimiento: str = ""
    universidad: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
