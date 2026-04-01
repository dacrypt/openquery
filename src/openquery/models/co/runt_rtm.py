"""RUNT RTM data model — Colombian vehicle technical inspection."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RuntRtmResult(BaseModel):
    """RTM (Revisión Técnico-Mecánica) status.

    Source: https://www.rfrfrunt.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    tiene_rtm: bool = False
    cda: str = ""  # Centro de Diagnóstico Automotor
    numero_certificado: str = ""
    fecha_expedicion: str = ""
    fecha_vencimiento: str = ""
    estado: str = ""  # "Vigente", "Vencido"
    resultado: str = ""  # "Aprobado", "Rechazado"
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
