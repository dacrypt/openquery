"""Guatemala NIT data model — SAT tax registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GtNitResult(BaseModel):
    """Guatemala NIT lookup result.

    Source: https://portal.sat.gob.gt/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    nit: str = ""
    nombre: str = ""
    estado: str = ""
    tipo_contribuyente: str = ""
    domicilio_fiscal: str = ""
    departamento: str = ""
    municipio: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
