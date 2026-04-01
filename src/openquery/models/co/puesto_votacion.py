"""Puesto de Votación data model — Colombian voting station lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PuestoVotacionResult(BaseModel):
    """Voting station lookup from Registraduría.

    Source: https://wsp.registraduria.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    nombre: str = ""
    departamento: str = ""
    municipio: str = ""
    puesto: str = ""
    direccion: str = ""
    mesa: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
