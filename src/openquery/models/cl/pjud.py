"""PJUD data model — Chilean judicial records (Poder Judicial)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CausaJudicial(BaseModel):
    """A single judicial case from the Chilean PJUD system."""

    rol: str = ""
    tribunal: str = ""
    materia: str = ""
    estado: str = ""
    fecha: str = ""
    caratulado: str = ""


class PjudResult(BaseModel):
    """Judicial case records from Chile's PJUD (Oficina Judicial Virtual).

    Source: https://oficinajudicialvirtual.pjud.cl/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    consulta: str = ""  # RUT or nombre queried
    causas: list[CausaJudicial] = Field(default_factory=list)
    total_causas: int = 0
    audit: Any | None = Field(default=None, exclude=True)
