"""Honduras RNP data model — identity / DNI registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HnRnpResult(BaseModel):
    """Honduras RNP identity registry lookup result.

    Source: https://www.rnp.hn/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    dni: str = ""
    nombre: str = ""
    birth_date: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
