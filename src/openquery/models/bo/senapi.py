"""Bolivia SENAPI trademark/patent registry data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SenapiResult(BaseModel):
    """Bolivia SENAPI trademark/patent registry lookup result.

    Source: https://www.senapi.gob.bo/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    trademark_name: str = ""
    owner: str = ""
    status: str = ""
    registration_date: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
