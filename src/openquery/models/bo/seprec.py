"""Bolivia SEPREC company registry data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SeprecResult(BaseModel):
    """Bolivia SEPREC company registry lookup result.

    Source: https://miempresa.seprec.gob.bo/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    nit: str = ""
    registration_status: str = ""
    folio: str = ""
    legal_representative: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
