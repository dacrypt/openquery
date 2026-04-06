"""Basel AML Index data model — country AML risk score."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BaselAmlResult(BaseModel):
    """Basel AML Index result.

    Source: https://index.baselgovernance.org/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    country: str = ""
    aml_score: float = 0.0
    aml_rank: int = 0
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
