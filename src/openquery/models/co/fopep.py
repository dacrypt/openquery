"""FOPEP data model — Colombian pensioners payroll."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FopepResult(BaseModel):
    """FOPEP pension payroll lookup.

    Source: https://www.fopep.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    nombre: str = ""
    esta_en_nomina: bool = False
    entidad_pagadora: str = ""
    tipo_pension: str = ""
    estado: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
