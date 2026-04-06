"""Nicaragua MARENA environmental permits model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NiMarenaResult(BaseModel):
    """Nicaragua MARENA environmental permits result.

    Source: https://www.marena.gob.ni/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    permit_type: str = ""
    status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
