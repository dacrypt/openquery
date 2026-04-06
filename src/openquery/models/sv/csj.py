"""El Salvador court cases data model — CSJ."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SvCsjResult(BaseModel):
    """El Salvador CSJ court case lookup result.

    Source: https://www.csj.gob.sv/consulta-publica/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    case_number: str = ""
    court: str = ""
    status: str = ""
    parties: list[str] = Field(default_factory=list)
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
