"""Brazil BACEN PTAX data model — USD/BRL exchange rates."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BrBacenPtaxResult(BaseModel):
    """Brazil BACEN PTAX exchange rate result.

    Source: https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    date: str = ""
    buy_rate: float | None = None
    sell_rate: float | None = None
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
