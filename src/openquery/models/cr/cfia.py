"""CFIA data model — Costa Rica engineer/architect professional registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CfiaResult(BaseModel):
    """Costa Rica CFIA professional registry lookup.

    Source: https://www.cfia.or.cr/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    professional_name: str = ""
    license_number: str = ""
    profession: str = ""
    membership_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
