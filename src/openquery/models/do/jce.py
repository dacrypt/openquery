"""Dominican Republic JCE data model — cedula verification."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DoJceResult(BaseModel):
    """Dominican Republic JCE cedula verification result.

    Source: https://dataportal.jce.gob.do/sarc/validar-certificacion-cedula/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    nombre: str = ""
    estado: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
