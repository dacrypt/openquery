"""Guatemala Registro Mercantil data model — company registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GtRegistroMercantilResult(BaseModel):
    """Guatemala Registro Mercantil company registry lookup result.

    Source: https://eregistros.registromercantil.gob.gt/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    registration_status: str = ""
    folio: str = ""
    company_type: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
