"""IEA Global EV data model — EV sales/stock/share by country."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IeaEvDataPoint(BaseModel):
    """A single annual EV data observation."""

    year: str = ""
    value: str = ""


class IntlIeaEvResult(BaseModel):
    """IEA Global EV Outlook data result.

    Source: https://api.iea.org/evs
    """

    country: str = ""
    parameter: str = ""
    data_points: list[IeaEvDataPoint] = Field(default_factory=list)
    details: str = ""
    queried_at: datetime = Field(default_factory=datetime.now)
    audit: Any | None = Field(default=None, exclude=True)
