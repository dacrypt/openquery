"""Uruguay INE statistics portal model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UyIneResult(BaseModel):
    """Uruguay INE statistical indicator result.

    Source: https://www.ine.gub.uy/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    indicator: str = ""
    value: str = ""
    period: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
