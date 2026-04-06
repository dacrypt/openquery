"""ANT Agencia de Tierras land restitution data model — Colombia."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgenciaTierrasResult(BaseModel):
    """ANT land restitution/formalization case lookup.

    Source: https://www.agenciadetierras.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    case_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
