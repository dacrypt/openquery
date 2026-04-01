"""Mi Casa Ya data model — Colombian housing subsidies."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SubsidioVivienda(BaseModel):
    """A housing subsidy record."""

    programa: str = ""
    estado: str = ""
    valor: str = ""
    fecha: str = ""
    proyecto: str = ""
    municipio: str = ""


class MiCasaYaResult(BaseModel):
    """Mi Casa Ya housing subsidy lookup.

    Source: https://www.minvivienda.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    nombre: str = ""
    tiene_subsidio: bool = False
    subsidios: list[SubsidioVivienda] = Field(default_factory=list)
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
