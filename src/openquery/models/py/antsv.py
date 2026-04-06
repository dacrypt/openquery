"""Paraguay ANTSV data model — vehicle tax value lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PyAntsvResult(BaseModel):
    """Paraguay ANTSV vehicle taxable value result.

    Source: https://ruhr.antsv.gov.py/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    brand: str = ""
    model: str = ""
    year: str = ""
    taxable_value: str = ""
    tax_amount: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
