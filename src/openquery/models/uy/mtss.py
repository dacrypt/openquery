"""MTSS data model — Uruguay ministry of labor employer data."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MtssResult(BaseModel):
    """Uruguay MTSS labor ministry employer data lookup.

    Source: https://www.gub.uy/ministerio-trabajo-seguridad-social/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    employer_name: str = ""
    compliance_status: str = ""
    industry: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
