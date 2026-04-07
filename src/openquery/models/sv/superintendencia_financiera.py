"""Superintendencia Financiera data model — El Salvador SSF banking statistics."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SvSuperintendenciaFinancieraResult(BaseModel):
    """El Salvador SSF banking and financial statistics lookup.

    Source: https://www.ssf.gob.sv/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    indicator: str = ""
    indicator_name: str = ""
    value: str = ""
    period: str = ""
    institution: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
