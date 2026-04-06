"""WIPO Global Brand Database data model — worldwide trademark registrations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WipoTrademark(BaseModel):
    """A trademark entry from WIPO Global Brand Database."""

    name: str = ""
    owner: str = ""
    jurisdiction: str = ""
    status: str = ""
    application_number: str = ""


class IntlWipoResult(BaseModel):
    """WIPO Global Brand Database trademark search result.

    Source: https://branddb.wipo.int/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total: int = 0
    trademarks: list[WipoTrademark] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
