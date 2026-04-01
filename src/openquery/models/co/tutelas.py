"""Tutelas data model — Colombian constitutional protection actions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TutelaEntry(BaseModel):
    """A tutela record."""

    radicado: str = ""
    accionante: str = ""
    accionado: str = ""
    derecho_invocado: str = ""
    fecha_presentacion: str = ""
    despacho: str = ""
    estado: str = ""
    fallo: str = ""


class TutelasResult(BaseModel):
    """Tutela (constitutional protection action) lookup.

    Source: https://consultaprocesos.ramajudicial.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    nombre: str = ""
    total_tutelas: int = 0
    tutelas: list[TutelaEntry] = Field(default_factory=list)
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
