"""Nicaragua SINARE data model — public company registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NiRegistroPublicoResult(BaseModel):
    """Nicaragua SINARE company registry lookup result.

    Source: https://www.registropublico.gob.ni/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    company_name: str = ""
    department: str = ""
    nam: str = ""
    status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
