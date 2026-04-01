"""Supercias data model — Ecuador company registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SuperciasResult(BaseModel):
    """Company data from Ecuador's Superintendencia de Companias.

    Source: https://appscvsgen.supercias.gob.ec/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    tipo_busqueda: str = ""
    razon_social: str = ""
    ruc: str = ""
    estado: str = ""
    fecha_constitucion: str = ""
    representante_legal: str = ""
    objeto_social: str = ""
    capital: str = ""
    direccion: str = ""
    audit: Any | None = Field(default=None, exclude=True)
