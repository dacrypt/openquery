"""SENESCYT data model — Ecuador professional degree verification."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TituloProfesional(BaseModel):
    """Single professional degree record."""

    titulo: str = ""
    institucion: str = ""
    tipo: str = ""
    nivel: str = ""
    fecha_registro: str = ""
    numero_registro: str = ""


class SenescytResult(BaseModel):
    """Professional degree data from Ecuador's SENESCYT.

    Source: https://www.senescyt.gob.ec/web/guest/consultas
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    titulos: list[TituloProfesional] = Field(default_factory=list)
    total_titulos: int = 0
    audit: Any | None = Field(default=None, exclude=True)
