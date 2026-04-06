"""CNE data model — Venezuela electoral registry / cedula lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CneResult(BaseModel):
    """Venezuela electoral registry lookup by cedula.

    Source: http://www.cne.gob.ve/web/registro_electoral/registro_electoral.php
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    nombre: str = ""
    centro_votacion: str = ""
    municipio: str = ""
    estado: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
