"""Certificado de Tradición y Libertad data model — Colombian property title."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AnotacionTradicion(BaseModel):
    """An annotation in the property title."""

    numero: str = ""
    fecha: str = ""
    especificacion: str = ""
    radicacion: str = ""
    valor_acto: str = ""
    personas: str = ""


class CertificadoTradicionResult(BaseModel):
    """Property title certificate (Certificado de Tradición y Libertad).

    Source: https://www.supernotariado.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    matricula_inmobiliaria: str = ""
    circulo_registral: str = ""
    direccion_predio: str = ""
    tipo_predio: str = ""  # "Urbano", "Rural"
    departamento: str = ""
    municipio: str = ""
    propietario_actual: str = ""
    total_anotaciones: int = 0
    anotaciones: list[AnotacionTradicion] = Field(default_factory=list)
    tiene_gravamenes: bool = False
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
