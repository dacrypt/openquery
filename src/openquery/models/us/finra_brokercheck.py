"""FINRA BrokerCheck data model — US broker/advisor verification."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FinraBrokercheckResult(BaseModel):
    """FINRA BrokerCheck broker/advisor verification result.

    Source: https://brokercheck.finra.org/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    broker_name: str = ""
    crd_number: str = ""
    status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
