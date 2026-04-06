"""Nicaragua CSE data model — electoral/cedula lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NiCseResult(BaseModel):
    """Nicaragua CSE voter/cedula lookup result.

    Source: https://www.cse.gob.ni/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    nombre: str = ""
    voting_center: str = ""
    municipality: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
