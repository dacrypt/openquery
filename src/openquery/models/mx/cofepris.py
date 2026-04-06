"""Mexico COFEPRIS data model — health product sanitary registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CofeprisResult(BaseModel):
    """COFEPRIS health product sanitary registry lookup result.

    Source: https://www.gob.mx/cofepris
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    product_name: str = ""
    registration_number: str = ""
    status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
