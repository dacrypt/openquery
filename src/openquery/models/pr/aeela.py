"""Puerto Rico LUMA/AEE electric utility data model — account status lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AeelaResult(BaseModel):
    """LUMA/AEE electric utility account status lookup result.

    Source: https://lumapr.com/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    account_number: str = ""
    account_status: str = ""
    balance: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
