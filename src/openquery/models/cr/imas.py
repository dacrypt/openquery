"""IMAS data model — Costa Rica social programs registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ImasResult(BaseModel):
    """Costa Rica IMAS social programs beneficiary lookup.

    Source: https://www.imas.go.cr/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    beneficiary_name: str = ""
    program_name: str = ""
    beneficiary_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
