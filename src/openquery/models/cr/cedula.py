"""Costa Rica cedula data model — TSE voter registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CrCedulaResult(BaseModel):
    """Costa Rica cedula lookup result.

    Source: https://www.consulta.tse.go.cr/consulta_persona/consulta_cedula.aspx
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    nombre: str = ""
    primer_apellido: str = ""
    segundo_apellido: str = ""
    fecha_nacimiento: str = ""
    sexo: str = ""
    provincia: str = ""
    canton: str = ""
    distrito: str = ""
    defuncion: bool = False
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
