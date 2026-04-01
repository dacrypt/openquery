"""Estado de Cédula de Extranjería data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EstadoCedulaExtranjeriaResult(BaseModel):
    """Foreign national ID card status from Migración Colombia.

    Source: https://apps.migracioncolombia.gov.co/consultaCedulas/pages/home.jsf
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula_extranjeria: str = ""
    fecha_expedicion: str = ""
    fecha_vencimiento: str = ""
    estado: str = ""  # "Vigente", "Vencida", "Cancelada", etc.
    nombre: str = ""
    nacionalidad: str = ""
    codigo_verificacion: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
