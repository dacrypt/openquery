"""AFIP CUIT data model — Argentine federal taxpayer registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AfipCuitResult(BaseModel):
    """Taxpayer info from Argentina's AFIP padron (constancia de inscripcion).

    Source: https://seti.afip.gob.ar/padron-puc-constancia-internet/ConsultaConstanciaAction.do
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cuit: str = ""
    razon_social: str = ""
    tipo_persona: str = ""  # "Física", "Jurídica"
    estado: str = ""  # "ACTIVO", "INACTIVO"
    actividades: list[str] = Field(default_factory=list)
    domicilio_fiscal: str = ""
    regimen_impositivo: str = ""
    fecha_contrato_social: str = ""
    audit: Any | None = Field(default=None, exclude=True)
