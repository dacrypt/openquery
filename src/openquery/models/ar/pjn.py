"""PJN data model — Argentine federal judicial records."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CausaPjn(BaseModel):
    """A single judicial case from Argentina's PJN (Poder Judicial de la Nacion)."""

    numero: str = ""
    fuero: str = ""
    juzgado: str = ""
    caratula: str = ""
    estado: str = ""
    fecha: str = ""


class PjnResult(BaseModel):
    """Federal judicial case records from Argentina's PJN.

    Source: https://scw.pjn.gov.ar/scw/home.seam
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    consulta: str = ""  # nombre or CUIT queried
    causas: list[CausaPjn] = Field(default_factory=list)
    total_causas: int = 0
    audit: Any | None = Field(default=None, exclude=True)
