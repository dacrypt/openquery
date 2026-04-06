"""OSINERGMIN energy/mining supervisor data model — Peru."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OsinergminResult(BaseModel):
    """OSINERGMIN supervised energy/mining entity lookup.

    Source: https://www.osinergmin.gob.pe/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
