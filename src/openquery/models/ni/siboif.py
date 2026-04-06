"""Nicaragua SIBOIF banking regulator model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NiSiboifResult(BaseModel):
    """Data from Nicaragua SIBOIF supervised entities registry.

    Source: https://www.siboif.gob.ni/
    """

    search_term: str = ""
    entity_name: str = ""
    license_status: str = ""
    entity_type: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
