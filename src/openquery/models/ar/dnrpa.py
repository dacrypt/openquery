"""DNRPA data model — Argentine vehicle registry (Direccion Nacional de los Registros de la Propiedad del Automotor)."""  # noqa: E501

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DnrpaResult(BaseModel):
    """Vehicle registry info from Argentina's DNRPA.

    Source: https://www.dnrpa.gov.ar/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    dominio: str = ""  # Argentine plate / dominio
    registro_seccional: str = ""
    localidad: str = ""
    provincia: str = ""
    tipo_vehiculo: str = ""
    audit: Any | None = Field(default=None, exclude=True)
