"""REPET data model — Argentine terrorism financing registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RepetResult(BaseModel):
    """REPET (Registro de Personas y Entidades Vinculadas al Terrorismo) list (Argentina).

    Source: https://www.argentina.gob.ar/uif/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    is_listed: bool = False
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
