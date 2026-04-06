"""SUNEDU university accreditation data model — Peru."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SuneduResult(BaseModel):
    """SUNEDU university accreditation lookup.

    Source: https://www.sunedu.gob.pe/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    university_name: str = ""
    accreditation_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
