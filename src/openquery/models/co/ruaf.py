"""RUAF data model — Colombian unified affiliates registry (SISPRO)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RuafAfiliacion(BaseModel):
    """An affiliation record from RUAF/SISPRO."""

    subsistema: str = ""  # "Salud", "Pensiones", "Riesgos Laborales", etc.
    administradora: str = ""
    estado: str = ""
    regimen: str = ""
    fecha_afiliacion: str = ""


class RuafResult(BaseModel):
    """RUAF/SISPRO unified affiliates registry results.

    Source: https://rufruf.minsalud.gov.co/RuafUI/Consultas
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    tipo_documento: str = ""
    nombre: str = ""
    afiliaciones: list[RuafAfiliacion] = Field(default_factory=list)
    total_afiliaciones: int = 0
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
