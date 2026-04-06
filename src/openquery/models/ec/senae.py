"""SENAE customs declarations data model — Ecuador."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SenaeResult(BaseModel):
    """SENAE customs declaration status lookup.

    Source: https://www.aduana.gob.ec/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    declaration_number: str = ""
    status: str = ""
    importer: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
