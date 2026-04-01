"""Poder Judicial data model — Peruvian judicial records."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExpedienteJudicial(BaseModel):
    """Single judicial case record."""

    numero: str = ""
    juzgado: str = ""
    materia: str = ""
    estado: str = ""
    fecha: str = ""
    partes: str = ""


class PoderJudicialResult(BaseModel):
    """Judicial case records from Peru's Poder Judicial (CEJ).

    Source: https://cej.pj.gob.pe/cej/forms/busquedaform.html
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    total_expedientes: int = 0
    expedientes: list[ExpedienteJudicial] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
