"""Ecuador Superbancos data model — supervised financial entities."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SuperbancosResult(BaseModel):
    """Superintendencia de Bancos supervised entities lookup result.

    Source: https://www.superbancos.gob.ec/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    entity_name: str = ""
    entity_type: str = ""
    supervision_status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
