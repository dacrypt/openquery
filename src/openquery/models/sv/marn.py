"""MARN data model — El Salvador environmental permits."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MarnResult(BaseModel):
    """El Salvador MARN environmental permit lookup.

    Source: https://www.marn.gob.sv/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    permit_number: str = ""
    permit_type: str = ""
    permit_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
