"""SRI RUC data model — Ecuador taxpayer registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SriRucResult(BaseModel):
    """Taxpayer data from Ecuador's SRI (Servicio de Rentas Internas).

    Source: https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet/rest/ConsolidadoContribuyente/obtenerPorNumerosRuc
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    ruc: str = ""
    razon_social: str = ""
    nombre_comercial: str = ""
    estado: str = ""
    actividad_economica: str = ""
    direccion: str = ""
    tipo_contribuyente: str = ""
    obligado_contabilidad: str = ""
    fecha_inicio_actividades: str = ""
    audit: Any | None = Field(default=None, exclude=True)
