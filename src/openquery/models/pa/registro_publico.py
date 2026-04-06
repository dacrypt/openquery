"""Panama Registro Publico data model — company registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RegistroPublicoResult(BaseModel):
    """Panama Registro Publico company registry lookup result.

    Source: https://www.rp.gob.pa/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    folio: str = ""
    registration_status: str = ""
    directors: list[str] = Field(default_factory=list)
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
