"""Honduras company registry data model — Registro Mercantil."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HnEmpresaResult(BaseModel):
    """Honduras company registry lookup result.

    Source: https://registromercantil.ccichonduras.org/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    company_type: str = ""
    registration_date: str = ""
    legal_representative: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
