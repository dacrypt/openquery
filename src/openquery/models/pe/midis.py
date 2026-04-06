"""MIDIS social programs beneficiary data model — Peru."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MidisResult(BaseModel):
    """MIDIS social program beneficiary status lookup.

    Source: https://www.midis.gob.pe/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    dni: str = ""
    nombre: str = ""
    programs: list[str] = Field(default_factory=list)
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
