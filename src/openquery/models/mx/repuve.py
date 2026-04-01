"""REPUVE data model — Mexican stolen vehicle registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RepuveResult(BaseModel):
    """Vehicle status from Mexico's REPUVE (Registro Publico Vehicular).

    Source: https://www2.repuve.gob.mx/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    niv: str = ""  # NIV = VIN in Mexico
    estatus_robo: str = ""  # "Sin reporte", "Con reporte", "Recuperado"
    marca: str = ""
    modelo: str = ""
    anio: str = ""
    audit: Any | None = Field(default=None, exclude=True)
