"""Brazil INSS data model — social security contribution lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InssResult(BaseModel):
    """INSS social security contribution lookup result.

    Source: https://meu.inss.gov.br/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cpf: str = ""
    contribution_status: str = ""
    benefit_type: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
