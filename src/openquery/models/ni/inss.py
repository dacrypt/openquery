"""Nicaragua INSS social security model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NiInssResult(BaseModel):
    """Data from Nicaragua INSS social security registry.

    Source: https://www.inss.gob.ni/
    """

    cedula: str = ""
    affiliation_status: str = ""
    employer: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
