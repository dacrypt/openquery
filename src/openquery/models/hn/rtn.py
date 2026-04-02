"""Honduras RTN data model — SAR tax registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HnRtnResult(BaseModel):
    """Honduras RTN lookup result.

    Source: https://www.sar.gob.hn/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    rtn: str = ""
    nombre: str = ""
    estado: str = ""
    tipo_contribuyente: str = ""
    actividad_economica: str = ""
    direccion: str = ""
    departamento: str = ""
    municipio: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
