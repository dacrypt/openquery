"""AJAM data model — Bolivia mining concessions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AjamResult(BaseModel):
    """Bolivia AJAM mining concessions lookup.

    Source: https://www.ajam.gob.bo/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    concession_name: str = ""
    holder: str = ""
    status: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
