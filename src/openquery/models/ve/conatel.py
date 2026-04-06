"""CONATEL telecom regulator data model — Venezuela."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConatelResult(BaseModel):
    """CONATEL licensed telecom operator lookup.

    Source: https://www.conatel.gob.ve/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    operator_name: str = ""
    license_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
