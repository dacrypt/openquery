"""Uruguay BCU central bank supervised entities model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BcuResult(BaseModel):
    """BCU supervised entity result for Uruguay.

    Source: https://www.bcu.gub.uy/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    entity_name: str = ""
    entity_type: str = ""
    supervision_status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
