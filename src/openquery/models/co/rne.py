"""RNE data model — Registro Nacional de Números Excluidos (Do Not Call)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RneResult(BaseModel):
    """Do Not Call registry result from CRC (Comisión de Regulación de Comunicaciones).

    Source: https://tramitescrcom.gov.co/tramites/publico/rne/loginRNE.xhtml
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    consulta: str = ""  # phone number or email queried
    tipo_consulta: str = ""  # "telefono" or "email"
    esta_excluido: bool = False
    fecha_registro: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
