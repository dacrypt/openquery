"""Dominican Republic RNC data model — DGII tax registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DoRncResult(BaseModel):
    """Dominican Republic RNC/cedula lookup result.

    Source: https://dgii.gov.do/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    rnc: str = ""
    nombre: str = ""
    nombre_comercial: str = ""
    categoria: str = ""
    regimen_pagos: str = ""
    estado: str = ""
    actividad_economica: str = ""
    administracion_local: str = ""
    audit: Any | None = Field(default=None, exclude=True)
