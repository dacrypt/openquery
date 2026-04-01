"""JEP data model — Colombian transitional justice processes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JepResult(BaseModel):
    """JEP (Jurisdicción Especial para la Paz) case lookup.

    Source: https://www.jep.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    tiene_procesos: bool = False
    total_resultados: int = 0
    resultados: list[dict] = Field(default_factory=list)
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
