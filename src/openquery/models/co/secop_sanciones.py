"""SECOP Sanciones data model — Colombian contractor sanctions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SecopSancion(BaseModel):
    """A single contractor sanction from SECOP."""

    proveedor: str = ""
    nit: str = ""
    tipo_sancion: str = ""
    entidad: str = ""
    fecha_sancion: str = ""
    valor: str = ""
    estado: str = ""


class SecopSancionesResult(BaseModel):
    """SECOP contractor sanctions results.

    Source: https://www.datos.gov.co/resource/4n4q-k399.json
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    total: int = 0
    sanciones: list[SecopSancion] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
