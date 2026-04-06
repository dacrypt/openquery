"""INFONAVIT housing credit data model — Mexico."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InfonavitResult(BaseModel):
    """INFONAVIT housing credit status lookup.

    Source: https://portalmx.infonavit.org.mx/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    nss: str = ""
    credit_status: str = ""
    balance: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
