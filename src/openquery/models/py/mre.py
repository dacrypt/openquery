"""Paraguay MRE consular/passport status model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PyMreResult(BaseModel):
    """Data from Paraguay MRE consular passport registry.

    Source: https://www.mre.gov.py/
    """

    passport_number: str = ""
    status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
