"""Professional registration data model — Argentina."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MatriculaProfesionalResult(BaseModel):
    """Argentina professional registration lookup.

    Source: varies by council
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    nombre: str = ""
    profession: str = ""
    license_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
