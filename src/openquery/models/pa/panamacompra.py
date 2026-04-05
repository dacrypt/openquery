"""Panama PanamaCompra data model — government contracts (OCDS API)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PanamaCompraContract(BaseModel):
    ocid: str = ""
    title: str = ""
    description: str = ""
    status: str = ""
    value: str = ""
    currency: str = ""
    buyer: str = ""
    supplier: str = ""
    date: str = ""


class PanamaCompraResult(BaseModel):
    """Panama PanamaCompra contracts lookup result.

    Source: https://ocdsv2dev.panamacompraencifras.gob.pa/api
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total: int = 0
    contracts: list[PanamaCompraContract] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
