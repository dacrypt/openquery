"""Estado Trámite de Cédula data model — Colombian ID card processing status."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EstadoTramiteCedulaResult(BaseModel):
    """Cédula processing/issuance status from Registraduría.

    Source: https://wsp.registraduria.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    estado_tramite: str = ""  # "En proceso", "Listo para entrega", "Entregado"
    fecha_solicitud: str = ""
    registraduria: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
