"""ANT Citaciones data model — Ecuador traffic citations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Citacion(BaseModel):
    """Single traffic citation record."""

    numero: str = ""
    fecha: str = ""
    tipo: str = ""
    monto: str = ""
    estado: str = ""
    puntos: str = ""


class AntCitacionesResult(BaseModel):
    """Traffic citation data from Ecuador's ANT (Agencia Nacional de Transito).

    Source: https://consultaweb.ant.gob.ec/PortalWEB/paginas/clientes/clp_json_consulta_persona.jsp
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    citaciones: list[Citacion] = Field(default_factory=list)
    total_citaciones: int = 0
    puntos_licencia: str = ""
    audit: Any | None = Field(default=None, exclude=True)
