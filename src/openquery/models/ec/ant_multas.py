"""ANT Multas data model — Ecuador traffic fines."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Multa(BaseModel):
    """Single traffic fine record."""

    numero: str = ""
    fecha: str = ""
    tipo: str = ""
    monto: str = ""
    estado: str = ""
    puntos: str = ""
    placa: str = ""
    descripcion: str = ""


class AntMultasResult(BaseModel):
    """Traffic fine data from Ecuador's ANT (Agencia Nacional de Transito).

    Source: https://consultaweb.ant.gob.ec/PortalWEB/paginas/clientes/clp_criterio_consulta.jsp
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_value: str = ""
    total_multas: int = 0
    total_amount: str = ""
    points_balance: str = ""
    multas: list[Multa] = Field(default_factory=list)
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
