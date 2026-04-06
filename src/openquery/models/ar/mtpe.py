"""MTPE employer lookup data model — Argentina."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MtpeResult(BaseModel):
    """Argentina Ministerio de Trabajo employer lookup.

    Source: https://www.argentina.gob.ar/trabajo
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cuit: str = ""
    employer_name: str = ""
    registration_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
