"""MINEM mining concessions data model — Peru."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MinemResult(BaseModel):
    """MINEM mining concession rights lookup.

    Source: https://www.minem.gob.pe/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    concession_name: str = ""
    holder: str = ""
    status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
