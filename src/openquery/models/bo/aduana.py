"""Aduana data model — Bolivia customs declarations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AduanaResult(BaseModel):
    """Bolivia Aduana Nacional customs declaration lookup.

    Source: https://www.aduana.gob.bo/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    declaration_number: str = ""
    declarant_name: str = ""
    customs_status: str = ""
    declaration_date: str = ""
    goods_description: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
