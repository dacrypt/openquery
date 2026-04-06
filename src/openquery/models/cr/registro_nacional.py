"""Registro Nacional data model — Costa Rica company/vehicle lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CrRegistroNacionalResult(BaseModel):
    """Costa Rica Registro Nacional company lookup.

    Source: https://www.rnpdigital.com/personas_juridicas/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    cedula_juridica: str = ""
    status: str = ""
    legal_representative: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
