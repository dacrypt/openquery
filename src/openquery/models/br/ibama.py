"""IBAMA environmental sanctions data model — Brazil."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IbamaResult(BaseModel):
    """IBAMA environmental fines lookup.

    Source: https://www.ibama.gov.br/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total_fines: int = 0
    fine_amount: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
