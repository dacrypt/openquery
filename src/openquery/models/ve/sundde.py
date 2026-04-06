"""SUNDDE data model — Venezuela price regulation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SunddeResult(BaseModel):
    """SUNDDE (Superintendencia Nacional para la Defensa de los Derechos Socioeconómicos) result.

    Source: https://www.sundde.gob.ve/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    product_name: str = ""
    regulated_price: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
