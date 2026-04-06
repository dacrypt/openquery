"""SINEACE data model — Peru educational accreditation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SineaceResult(BaseModel):
    """Educational accreditation data from Peru's SINEACE.

    Source: https://www.sineace.gob.pe/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    institution_name: str = ""
    accreditation_status: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
