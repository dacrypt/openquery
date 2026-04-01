"""Validar Policía data model — verify if a police officer is legitimate."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ValidarPoliciaResult(BaseModel):
    """Police officer validation result from Policía Nacional.

    Source: https://srvcnpc.policia.gov.co/PSC/frm_cnp_consulta.aspx
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    placa: str = ""
    carnet: str = ""
    es_policia_activo: bool = False
    nombre: str = ""
    grado: str = ""
    unidad: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
