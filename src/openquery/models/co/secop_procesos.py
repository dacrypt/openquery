"""SECOP Procesos data model — Colombian procurement processes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SecopProceso(BaseModel):
    """A single procurement process from SECOP."""

    entidad: str = ""
    nit_entidad: str = ""
    proceso: str = ""
    estado: str = ""
    tipo_proceso: str = ""
    valor_proceso: str = ""
    fecha_publicacion: str = ""
    url_proceso: str = ""


class SecopProcesosResult(BaseModel):
    """SECOP procurement processes results.

    Source: https://www.datos.gov.co/resource/p6dx-8zbt.json
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    total: int = 0
    procesos: list[SecopProceso] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
