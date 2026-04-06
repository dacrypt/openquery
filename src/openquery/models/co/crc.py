"""CRC telecom regulator data model — Colombia."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CrcResult(BaseModel):
    """CRC licensed telecom operators lookup.

    Source: https://www.crcom.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    operator_name: str = ""
    license_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
