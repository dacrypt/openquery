"""Brazil Receita CNAE data model — activity classification codes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BrReceitaCnaeResult(BaseModel):
    """Brazil CNAE activity code lookup result.

    Source: https://brasilapi.com.br/api/cnae/v1/{code}
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    code: str = ""
    description: str = ""
    section: str = ""
    division: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
