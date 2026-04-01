"""CNE Padron data model — Ecuador voter registration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CnePadronResult(BaseModel):
    """Voter registration data from Ecuador's CNE (Consejo Nacional Electoral).

    Source: https://lugarvotacion.cne.gob.ec/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    nombre: str = ""
    provincia: str = ""
    canton: str = ""
    parroquia: str = ""
    recinto: str = ""
    direccion: str = ""
    audit: Any | None = Field(default=None, exclude=True)
