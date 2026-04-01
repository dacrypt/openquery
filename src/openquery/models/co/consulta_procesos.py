"""Consulta de Procesos data model — Colombian judicial processes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProcesoJudicial(BaseModel):
    """A judicial process record."""

    radicacion: str = ""
    despacho: str = ""
    tipo_proceso: str = ""
    clase: str = ""
    sujetos: str = ""
    fecha_radicacion: str = ""
    fecha_ultima_actuacion: str = ""
    ultima_actuacion: str = ""


class ConsultaProcesosResult(BaseModel):
    """Rama Judicial process lookup results.

    Source: https://consultaprocesos.ramajudicial.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    nombre: str = ""
    total_procesos: int = 0
    procesos: list[ProcesoJudicial] = Field(default_factory=list)
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
