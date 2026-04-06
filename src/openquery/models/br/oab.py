"""OAB data model — Brazil lawyer verification."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OabResult(BaseModel):
    """OAB (Ordem dos Advogados do Brasil) lawyer verification result.

    Source: https://www.oab.org.br/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    oab_number: str = ""
    nome: str = ""
    estado: str = ""
    status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
