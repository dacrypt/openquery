"""EPA Envirofacts environmental facility data model — USA."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EpaEnvirofactsResult(BaseModel):
    """EPA Envirofacts environmental compliance lookup.

    Source: https://enviro.epa.gov/enviro/efservice/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    facility_name: str = ""
    compliance_status: str = ""
    violations: list[str] = Field(default_factory=list)
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
