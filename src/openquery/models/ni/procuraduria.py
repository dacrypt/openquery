"""Procuraduría data model — Nicaragua anticorruption public records."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NiProcuraduriaResult(BaseModel):
    """Nicaragua Procuraduría anticorruption public records lookup.

    Source: https://www.pgr.gob.ni/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    found: bool = False
    record_type: str = ""
    status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
