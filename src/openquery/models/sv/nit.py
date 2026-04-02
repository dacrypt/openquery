"""El Salvador NIT/DUI data model — DGII tax registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SvNitResult(BaseModel):
    """El Salvador NIT/DUI lookup result.

    Source: https://portaldgii.mh.gob.sv/ssc/serviciosinclave/consulta/duinit/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    dui: str = ""
    nit: str = ""
    nombre: str = ""
    estado_cuenta: str = ""
    homologado: bool = False
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
