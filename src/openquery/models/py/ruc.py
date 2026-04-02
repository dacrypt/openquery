"""Paraguay RUC data model — SET/DNIT tax registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PyRucResult(BaseModel):
    """Paraguay RUC lookup result.

    Source: https://servicios.set.gov.py/eset-publico/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    ruc: str = ""
    razon_social: str = ""
    nombre_fantasia: str = ""
    estado: str = ""
    tipo_contribuyente: str = ""
    actividad_economica: str = ""
    direccion: str = ""
    departamento: str = ""
    distrito: str = ""
    telefono: str = ""
    audit: Any | None = Field(default=None, exclude=True)
