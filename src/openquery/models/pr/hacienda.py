"""Puerto Rico Hacienda tax/merchant registry model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HaciendaResult(BaseModel):
    """Data from Puerto Rico Hacienda SURI merchant/taxpayer registry.

    Source: https://suri.hacienda.pr.gov/
    """

    search_value: str = ""
    merchant_name: str = ""
    tax_status: str = ""
    registration_status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
