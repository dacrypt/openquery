"""Autopase data model — TAG highway toll debt status (Chile)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AutopaseResult(BaseModel):
    """TAG account and debt status from Chile's Autopase portal.

    Source: https://www.autopase.cl/tag/estado
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    tag_status: str = ""
    debt_amount: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
