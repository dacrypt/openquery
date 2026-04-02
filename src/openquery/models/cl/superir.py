"""Superir data model — Chilean insolvency and bankruptcy registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BankruptcyProceeding(BaseModel):
    """A single bankruptcy/insolvency proceeding from Superir."""

    tipo_procedimiento: str = ""
    estado: str = ""
    tribunal: str = ""
    fecha_resolucion: str = ""
    veedor_liquidador: str = ""


class SuperirResult(BaseModel):
    """Superir insolvency/bankruptcy search results.

    Source: https://www.superir.gob.cl/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    rut: str = ""
    nombre: str = ""
    procedimientos: list[BankruptcyProceeding] = Field(default_factory=list)
    total_procedimientos: int = 0
    tiene_procedimiento: bool = False
    audit: Any | None = Field(default=None, exclude=True)
