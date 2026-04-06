"""Fotocivicas data model — CDMX photo enforcement fines."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FotocivicaViolation(BaseModel):
    """A single photo-enforced violation record."""

    folio: str = ""
    fecha: str = ""
    tipo: str = ""  # e.g. "Exceso de velocidad", "Semaforo en rojo"
    ubicacion: str = ""
    monto: str = ""
    estatus: str = ""


class FotocivicasResult(BaseModel):
    """Photo enforcement fines from CDMX fotocivicas portal.

    Source: https://www.tramites.cdmx.gob.mx/fotocivicas/public/
    """

    placa: str = ""
    total_violations: int = 0
    total_amount: str = ""
    violations: list[FotocivicaViolation] = Field(default_factory=list)
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
