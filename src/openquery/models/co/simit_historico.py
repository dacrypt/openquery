"""SIMIT Historico data model — Colombian historical traffic fines."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SimitCitacion(BaseModel):
    """A historical traffic citation from SIMIT."""

    numero: str = ""
    fecha: str = ""
    infraccion: str = ""
    estado: str = ""
    valor: str = ""
    secretaria: str = ""


class SimitHistoricoResult(BaseModel):
    """SIMIT historical traffic citations results.

    Source: https://www.datos.gov.co/resource/72nf-y4v3.json
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    total: int = 0
    citaciones: list[SimitCitacion] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
