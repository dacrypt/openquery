"""RNMC data model — Colombian National Registry of Corrective Measures."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MedidaCorrectiva(BaseModel):
    """A corrective measure entry."""

    tipo_medida: str = ""
    descripcion: str = ""
    fecha_imposicion: str = ""
    estado: str = ""
    autoridad: str = ""
    localidad: str = ""
    relato: str = ""


class RnmcResult(BaseModel):
    """RNMC (Registro Nacional de Medidas Correctivas) results.

    Source: https://srvcnpc.policia.gov.co/PSC/frm_cnp_consulta.aspx
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    nombre: str = ""
    tiene_medidas: bool = False
    total_medidas: int = 0
    medidas: list[MedidaCorrectiva] = Field(default_factory=list)
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
