"""CURP data model — Mexican population registry (RENAPO)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CurpResult(BaseModel):
    """CURP lookup result from Mexico's RENAPO.

    Source: https://consultas.curp.gob.mx/CurpSP/gobmx/ConsultaCURP
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    curp: str = ""
    nombre: str = ""
    apellido_paterno: str = ""
    apellido_materno: str = ""
    fecha_nacimiento: str = ""
    sexo: str = ""  # "H" or "M"
    estado_nacimiento: str = ""
    estatus: str = ""  # e.g., "RCN" (Registrado Con acta de Nacimiento)
    documento_probatorio: str = ""
    audit: Any | None = Field(default=None, exclude=True)
