"""CSJN data model — Argentine Supreme Court cases."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CsjnResult(BaseModel):
    """CSJN (Corte Suprema de Justicia de la Nación) court case result.

    Source: https://sj.csjn.gov.ar/sj/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    case_number: str = ""
    court: str = ""
    status: str = ""
    ruling: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
