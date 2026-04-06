"""CRIM property tax/catastro model — Puerto Rico."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CrimResult(BaseModel):
    """Data from Puerto Rico's CRIM property tax/catastro system.

    Source: https://catastro.crimpr.net/cdprpc/
    """

    account_number: str = ""
    property_value: str = ""
    tax_status: str = ""
    owner: str = ""
    address: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
