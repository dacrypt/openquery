"""Bolivia SICOES government contracts data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SicoesContract(BaseModel):
    """A single contract or tender record from SICOES."""

    code: str = ""
    entity: str = ""
    description: str = ""
    amount: str = ""
    status: str = ""
    date: str = ""


class SicoesResult(BaseModel):
    """Bolivia SICOES government contracts lookup result.

    Source: https://www.sicoes.gob.bo/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total: int = 0
    contracts: list[SicoesContract] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
