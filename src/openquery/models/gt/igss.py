"""IGSS data model — Guatemala social security affiliation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IgssResult(BaseModel):
    """Guatemala IGSS social security affiliation lookup.

    Source: https://www.igss.gob.gt/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    affiliation_number: str = ""
    affiliate_name: str = ""
    affiliation_status: str = ""
    employer: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
