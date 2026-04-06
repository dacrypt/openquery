"""Nicaragua MIFIC trade/industry registry model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NiMificResult(BaseModel):
    """Data from Nicaragua MIFIC trade and industry registry.

    Source: https://www.mific.gob.ni/
    """

    search_term: str = ""
    company_name: str = ""
    registration_status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
