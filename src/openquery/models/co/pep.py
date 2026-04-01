"""PEP (Politically Exposed Persons) data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PepEntry(BaseModel):
    """A PEP list entry."""

    nombre: str = ""
    cargo: str = ""
    entidad: str = ""
    fecha_vinculacion: str = ""
    estado: str = ""


class PepResult(BaseModel):
    """PEP screening results for Colombia.

    Source: Colombian government PEP lists / datos.gov.co
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    nombre_consultado: str = ""
    es_pep: bool = False
    match_count: int = 0
    registros: list[PepEntry] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
