"""RUES data model — Colombian unified business registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RuesEstablecimiento(BaseModel):
    """A business establishment from RUES."""

    nombre: str = ""
    matricula: str = ""
    estado: str = ""
    municipio: str = ""
    direccion: str = ""
    actividad_economica: str = ""


class RuesResult(BaseModel):
    """RUES (Registro Único Empresarial y Social) results.

    Source: https://www.rues.org.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    tipo_busqueda: str = ""  # "nit", "cedula", "nombre"
    razon_social: str = ""
    nit: str = ""
    estado_matricula: str = ""
    camara_comercio: str = ""
    fecha_matricula: str = ""
    representante_legal: str = ""
    tipo_organizacion: str = ""
    establecimientos: list[RuesEstablecimiento] = Field(default_factory=list)
    total_establecimientos: int = 0
    audit: Any | None = Field(default=None, exclude=True)
