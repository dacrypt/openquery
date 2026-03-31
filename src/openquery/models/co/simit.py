"""SIMIT data model — Colombian traffic fines."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass


class SimitResult(BaseModel):
    """Data from Colombia's SIMIT (Sistema Integrado de Información sobre
    Multas y Sanciones por Infracciones de Tránsito).

    Source: https://www.fcm.org.co/simit/#/estado-cuenta
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    comparendos: int = 0
    multas: int = 0
    acuerdos_pago: int = 0
    total_deuda: float = 0.0
    paz_y_salvo: bool = False
    historial: list[dict] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)  # AuditRecord when audit=True
