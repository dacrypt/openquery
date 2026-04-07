"""ANDE data model — Paraguay electricity utility account status."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AndeResult(BaseModel):
    """Paraguay ANDE electricity utility account lookup.

    Source: https://www.ande.gov.py/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    account_number: str = ""
    account_holder: str = ""
    account_status: str = ""
    balance: str = ""
    last_payment: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
