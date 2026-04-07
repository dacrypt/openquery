"""BCCR data model — Costa Rica central bank economic indicators."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BccrResult(BaseModel):
    """Costa Rica BCCR economic indicators lookup.

    Source: https://gee.bccr.fi.cr/indicadoreseconomicos/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    indicator: str = ""
    indicator_name: str = ""
    value: str = ""
    period: str = ""
    unit: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
