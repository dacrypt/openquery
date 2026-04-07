"""MIEM data model — Uruguay industry/energy ministry industrial registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MiemResult(BaseModel):
    """Uruguay MIEM industrial registry lookup.

    Source: https://www.gub.uy/ministerio-industria-energia-mineria/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    registration_number: str = ""
    industry_type: str = ""
    status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
