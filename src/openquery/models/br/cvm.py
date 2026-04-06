"""Brazil CVM data model — securities regulator company/fund lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CvmResult(BaseModel):
    """CVM securities regulator lookup result.

    Source: https://www.rad.cvm.gov.br/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    cnpj: str = ""
    registration_status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
