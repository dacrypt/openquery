"""SUNAT RUC data model — Peruvian tax registry (RUC)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SunatRucResult(BaseModel):
    """Tax registration from Peru's SUNAT.

    Full name: Superintendencia Nacional de Aduanas y Administracion Tributaria.

    Source: https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/FrameCriterioBusquedaWeb.jsp
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    ruc: str = ""
    razon_social: str = ""
    estado: str = ""  # ACTIVO, BAJA, SUSPENSION TEMPORAL
    condicion: str = ""  # HABIDO, NO HABIDO, NO HALLADO
    direccion: str = ""
    actividad_economica: str = ""
    regimen: str = ""  # GENERAL, ESPECIAL, MYPE, RUS
    tipo_contribuyente: str = ""  # PERSONA NATURAL, PERSONA JURIDICA
    fecha_inscripcion: str = ""
    audit: Any | None = Field(default=None, exclude=True)
