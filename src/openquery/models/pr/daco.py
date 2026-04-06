"""Puerto Rico DACO consumer affairs model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PrDacoResult(BaseModel):
    """Puerto Rico DACO consumer affairs result.

    Source: https://www.daco.pr.gov/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    license_status: str = ""
    complaints_count: int = 0
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
