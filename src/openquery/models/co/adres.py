"""ADRES data model — Colombian health insurance affiliation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AdresResult(BaseModel):
    """Health insurance affiliation from Colombia's ADRES (formerly FOSYGA).

    Source: https://aplicaciones.adres.gov.co/BDUA_Internet/Pages/ConsultarAfiliadoWeb_2.aspx
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    tipo_documento: str = ""
    nombre: str = ""
    estado_afiliacion: str = ""  # ACTIVO, RETIRADO, etc.
    regimen: str = ""  # CONTRIBUTIVO, SUBSIDIADO
    eps: str = ""  # Name of the EPS (health provider)
    tipo_afiliado: str = ""  # COTIZANTE, BENEFICIARIO
    municipio: str = ""
    departamento: str = ""
    fecha_afiliacion: str = ""
    fecha_efectiva: str = ""
    audit: Any | None = Field(default=None, exclude=True)  # AuditRecord when audit=True
