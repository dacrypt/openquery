"""INACIF data model — Guatemala forensic registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InacifResult(BaseModel):
    """Guatemala INACIF forensic registry lookup.

    Source: https://www.inacif.gob.gt/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    case_number: str = ""
    case_type: str = ""
    status: str = ""
    date_registered: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
