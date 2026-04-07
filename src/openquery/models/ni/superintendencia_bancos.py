"""Superintendencia Bancos data model — Nicaragua SIBOIF banking statistics."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NiSuperintendenciaBancosResult(BaseModel):
    """Nicaragua SIBOIF banking statistics lookup.

    Source: https://www.siboif.gob.ni/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    indicator: str = ""
    indicator_name: str = ""
    value: str = ""
    period: str = ""
    institution: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
