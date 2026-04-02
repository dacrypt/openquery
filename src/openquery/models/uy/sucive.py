"""Uruguay SUCIVE data model — vehicle patent/tax lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UySuciveResult(BaseModel):
    """Uruguay SUCIVE vehicle lookup result.

    Source: https://sucive.gub.uy/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    matricula: str = ""
    padron: str = ""
    departamento: str = ""
    marca: str = ""
    modelo: str = ""
    anio: str = ""
    valor_patente: str = ""
    deuda: str = ""
    estado: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
