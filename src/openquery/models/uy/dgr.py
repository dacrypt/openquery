"""Uruguay DGR data model — company/commerce registry lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UyDgrResult(BaseModel):
    """Uruguay DGR company/commerce registry lookup result.

    Source: https://portal.dgr.gub.uy/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    registration_status: str = ""
    company_type: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
