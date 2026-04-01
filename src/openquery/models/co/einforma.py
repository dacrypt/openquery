"""eInforma data model — Colombian business intelligence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EinformaResult(BaseModel):
    """eInforma business intelligence lookup.

    Source: https://www.einforma.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    tipo_busqueda: str = ""
    razon_social: str = ""
    nit: str = ""
    estado: str = ""
    actividad_economica: str = ""
    tamano_empresa: str = ""
    direccion: str = ""
    municipio: str = ""
    departamento: str = ""
    telefono: str = ""
    representante_legal: str = ""
    fecha_constitucion: str = ""
    encontrado: bool = False
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
