"""SEGIP data model — Bolivia identity service."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SegipResult(BaseModel):
    """Bolivia SEGIP identity service lookup.

    Source: https://www.segip.gob.bo/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    ci: str = ""
    nombre: str = ""
    document_status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
