"""Brazil banks data model — BrasilAPI bank list."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BrBankResult(BaseModel):
    """Brazil bank lookup result.

    Source: https://brasilapi.com.br/api/banks/v1/{code}
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    ispb: str = ""
    name: str = ""
    code: int = 0
    full_name: str = ""
    audit: Any | None = Field(default=None, exclude=True)
