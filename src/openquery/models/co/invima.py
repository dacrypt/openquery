"""INVIMA data model — Colombian health product/drug registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InvimaResult(BaseModel):
    """INVIMA (Instituto Nacional de Vigilancia de Medicamentos y Alimentos) product registry.

    Source: https://www.invima.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    product_name: str = ""
    registration_number: str = ""
    status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
