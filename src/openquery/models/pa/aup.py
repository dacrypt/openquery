"""Panama AUP data model — public utilities authority (ASEP) service providers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PaAupResult(BaseModel):
    """Panama AUP/ASEP public utilities provider result.

    Source: https://www.asep.gob.pa/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    provider_name: str = ""
    service_type: str = ""
    status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
