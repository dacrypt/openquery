"""DIAN RUT data model — Colombian tax registry status."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DianRutResult(BaseModel):
    """DIAN RUT (Registro Único Tributario) status.

    Source: https://muisca.dian.gov.co/WebRutMuisca/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    tipo_documento: str = ""
    nombre_razon_social: str = ""
    estado_rut: str = ""  # "Activo", "Inactivo", etc.
    nit: str = ""
    actividad_economica: str = ""
    direccion: str = ""
    municipio: str = ""
    departamento: str = ""
    responsabilidades: list[str] = Field(default_factory=list)
    fecha_inscripcion: str = ""
    audit: Any | None = Field(default=None, exclude=True)
