"""ENACOM telecom regulator data model — Argentina."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EnacomResult(BaseModel):
    """ENACOM licensed telecom operator lookup.

    Source: https://www.enacom.gob.ar/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    license_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
