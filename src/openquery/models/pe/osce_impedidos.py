"""OSCE Impedidos data model — Peruvian debarred contractors registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OsceImpedidosResult(BaseModel):
    """OSCE debarred/impedidos contractors registry (Peru).

    Source: https://www.osce.gob.pe/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    ruc: str = ""
    debarment_status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
