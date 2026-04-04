"""Interpol Red Notices data model — wanted persons lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InterpolNotice(BaseModel):
    """A Red Notice from Interpol."""

    entity_id: str = ""
    name: str = ""
    forename: str = ""
    date_of_birth: str = ""
    nationalities: list[str] = Field(default_factory=list)
    sex: str = ""
    charge: str = ""
    issuing_country: str = ""
    url: str = ""


class IntlInterpolResult(BaseModel):
    """Interpol Red Notices search result.

    Source: https://ws-public.interpol.int/notices/v1/red
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    total: int = 0
    notices: list[InterpolNotice] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
