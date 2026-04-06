"""InfraccionesCdmx data model — CDMX traffic infractions."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class InfraccionRecord(BaseModel):
    """A single traffic infraction record."""

    folio: str = ""
    fecha: str = ""
    descripcion: str = ""
    monto: str = ""
    estatus: str = ""


class InfraccionesCdmxResult(BaseModel):
    """Traffic infractions from CDMX portal.

    Source: https://infracciones.cdmx.gob.mx/
    """

    placa: str = ""
    total_infractions: int = 0
    total_amount: str = ""
    infractions: list[InfraccionRecord] = Field(default_factory=list)
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
