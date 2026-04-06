"""Paraguay Poder Judicial data model — court case lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PyPjResult(BaseModel):
    """Paraguay Poder Judicial court case lookup result.

    Source: https://www.csj.gov.py/consultacasojudicial
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    case_number: str = ""
    status: str = ""
    court: str = ""
    parties: str = ""
    last_action: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
