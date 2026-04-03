"""Bolivia NIT data model — SIN tax registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BoNitResult(BaseModel):
    """Bolivia NIT lookup result.

    Source: https://ov.impuestos.gob.bo/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    nit: str = ""
    razon_social: str = ""
    estado: str = ""
    tipo_contribuyente: str = ""
    actividad_economica: str = ""
    domicilio_fiscal: str = ""
    departamento: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
