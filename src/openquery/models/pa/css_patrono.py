"""Panama CSS Patrono data model — employer registration (Caja de Seguro Social)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PaCssPatronoResult(BaseModel):
    """Panama CSS employer/patrono lookup result.

    Source: https://w3.css.gob.pa/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    employer_name: str = ""
    registration_status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
