"""NOSIS data model — Argentine credit report."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NosisResult(BaseModel):
    """NOSIS credit report result for Argentine CUIT.

    Source: https://www.nosis.com/es
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cuit: str = ""
    company_name: str = ""
    credit_status: str = ""
    delinquency_status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
