"""Funcion Judicial data model — Ecuador judicial processes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProcesoJudicial(BaseModel):
    """Single judicial process record."""

    numero_causa: str = ""
    tipo: str = ""
    estado: str = ""
    fecha: str = ""
    juzgado: str = ""
    demandante: str = ""
    demandado: str = ""


class FuncionJudicialResult(BaseModel):
    """Judicial process data from Ecuador's Consejo de la Judicatura.

    Source: https://procesosjudiciales.funcionjudicial.gob.ec/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    procesos: list[ProcesoJudicial] = Field(default_factory=list)
    total_procesos: int = 0
    audit: Any | None = Field(default=None, exclude=True)
