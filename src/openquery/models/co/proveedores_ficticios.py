"""Proveedores Ficticios data model — DIAN fictitious providers list."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProveedorFicticioEntry(BaseModel):
    """A fictitious provider entry."""

    nit: str = ""
    razon_social: str = ""
    resolucion: str = ""
    fecha_resolucion: str = ""
    estado: str = ""


class ProveedoresFicticiosResult(BaseModel):
    """DIAN fictitious providers list screening.

    Source: https://www.datos.gov.co (DIAN open data)
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    es_proveedor_ficticio: bool = False
    match_count: int = 0
    registros: list[ProveedorFicticioEntry] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
