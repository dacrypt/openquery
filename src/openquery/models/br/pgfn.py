"""PGFN data model — Brazil tax debt registry (Dívida Ativa)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PgfnResult(BaseModel):
    """PGFN (Procuradoria-Geral da Fazenda Nacional) tax debt result.

    Source: https://www.regularize.pgfn.gov.br/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total_debt: str = ""
    debt_status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
