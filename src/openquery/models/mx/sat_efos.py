"""SAT EFOS data model — Mexican phantom taxpayer blacklist (69-B)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ContribuyenteEfos(BaseModel):
    """A single entry from Mexico's SAT 69-B blacklist (EFOS)."""

    rfc: str = ""
    nombre: str = ""
    situacion: str = ""  # "Presunto", "Definitivo", "Desvirtuado", "Sentencia Favorable"
    fecha_publicacion_dof: str = ""
    fecha_publicacion_sat: str = ""


class SatEfosResult(BaseModel):
    """SAT 69-B phantom taxpayer (EFOS) lookup result.

    Source: https://listados.sat.gob.mx/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    consulta: str = ""  # RFC or nombre queried
    contribuyentes: list[ContribuyenteEfos] = Field(default_factory=list)
    total_resultados: int = 0
    audit: Any | None = Field(default=None, exclude=True)
