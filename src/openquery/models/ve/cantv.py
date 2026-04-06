"""CANTV data model — Venezuela phone/internet service lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CantvResult(BaseModel):
    """Venezuela CANTV phone/internet service lookup.

    Source: https://www.cantv.com.ve/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    phone_number: str = ""
    service_status: str = ""
    plan: str = ""
    debt_amount: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
