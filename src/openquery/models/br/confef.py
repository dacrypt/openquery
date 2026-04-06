"""CONFEF physical education professional data model — Brazil."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConfefResult(BaseModel):
    """CONFEF physical education professional registry lookup.

    Source: https://www.confef.org.br/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cref_number: str = ""
    nome: str = ""
    status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
