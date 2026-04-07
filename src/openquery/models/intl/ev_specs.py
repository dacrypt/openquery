"""EV specs data model — Open EV Data battery/range specs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IntlEvSpecsResult(BaseModel):
    """Open EV Data vehicle specs result.

    Source: https://raw.githubusercontent.com/open-ev-data/open-ev-data-dataset/main/data/ev-data.json
    """

    brand: str = ""
    model: str = ""
    battery_capacity_kwh: str = ""
    range_km: str = ""
    fast_charge_kw: str = ""
    connector_type: str = ""
    details: str = ""
    matches: list[dict] = Field(default_factory=list)
    queried_at: datetime = Field(default_factory=datetime.now)
    audit: Any | None = Field(default=None, exclude=True)
