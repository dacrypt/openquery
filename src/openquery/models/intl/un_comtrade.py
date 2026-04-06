"""UN Comtrade data model — international trade statistics."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ComtradePartner(BaseModel):
    """A trade partner entry from UN Comtrade."""

    partner_code: str = ""
    partner_desc: str = ""
    trade_value: float | None = None
    flow: str = ""


class IntlUnComtradeResult(BaseModel):
    """UN Comtrade trade statistics result.

    Source: https://comtradeapi.un.org/public/v1/preview/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    reporter: str = ""
    commodity_code: str = ""
    total_trade_value: float | None = None
    partners: list[ComtradePartner] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
