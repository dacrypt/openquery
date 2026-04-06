"""MEC university accreditation data model — Brazil."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MecResult(BaseModel):
    """MEC (e-MEC) university accreditation lookup.

    Source: https://emec.mec.gov.br/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    institution_name: str = ""
    accreditation_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
