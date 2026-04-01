"""RNT Turismo data model — Colombian national tourism registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RntTurismoEntry(BaseModel):
    """A tourism registry entry."""

    rnt: str = ""
    razon_social: str = ""
    categoria: str = ""
    subcategoria: str = ""
    municipio: str = ""
    departamento: str = ""
    estado: str = ""
    fecha_registro: str = ""


class RntTurismoResult(BaseModel):
    """RNT (Registro Nacional de Turismo) results.

    Source: https://www.datos.gov.co/resource/2z2j-kxnj.json
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    total: int = 0
    registros: list[RntTurismoEntry] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
