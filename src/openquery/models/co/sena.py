"""Colombia SENA data model — certification/training verification."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SenaResult(BaseModel):
    """SENA certification and training verification result.

    Source: https://www.sena.edu.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    nombre: str = ""
    certification_status: str = ""
    program: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
