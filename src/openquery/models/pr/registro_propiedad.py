"""Puerto Rico property registry model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RegistroPropiedadResult(BaseModel):
    """Data from Puerto Rico property registry.

    Source: https://registrodelapropiedad.pr.gov/
    """

    search_value: str = ""
    property_number: str = ""
    owner: str = ""
    liens: str = ""
    property_value: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
