"""Nicaragua MINSA health registry model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NiMinsaResult(BaseModel):
    """Data from Nicaragua MINSA health establishment registry.

    Source: https://www.minsa.gob.ni/
    """

    search_term: str = ""
    establishment_name: str = ""
    permit_status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
