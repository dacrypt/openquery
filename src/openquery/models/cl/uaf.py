"""UAF data model — Chilean financial intelligence designated persons list."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UafResult(BaseModel):
    """UAF (Unidad de Analisis Financiero) designated persons list (Chile).

    Source: https://www.uaf.cl/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    is_designated: bool = False
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
