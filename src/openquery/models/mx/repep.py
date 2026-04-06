"""REPEP data model — Mexico do-not-call registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RepepResult(BaseModel):
    """REPEP (Registro Público para Evitar Publicidad) do-not-call lookup result.

    Source: https://repep.profeco.gob.mx/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    phone_number: str = ""
    is_registered: bool = False
    registration_date: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
