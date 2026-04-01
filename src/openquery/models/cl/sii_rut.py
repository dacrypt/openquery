"""SII RUT data model — Chilean taxpayer registry (Servicio de Impuestos Internos)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SiiRutResult(BaseModel):
    """Taxpayer info from Chile's SII (Servicio de Impuestos Internos).

    Source: https://www2.sii.cl/stc/noauthz
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    rut: str = ""
    razon_social: str = ""
    actividades_economicas: list[str] = Field(default_factory=list)
    estado: str = ""  # e.g., "Contribuyente hace Inicio de Actividades"
    fecha_inicio_actividades: str = ""
    tipo_contribuyente: str = ""  # e.g., "Persona Natural", "Persona Jurídica"
    audit: Any | None = Field(default=None, exclude=True)
