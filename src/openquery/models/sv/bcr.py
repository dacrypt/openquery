"""El Salvador BCR exchange rates / economic indicators model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SvBcrResult(BaseModel):
    """Data from El Salvador BCR economic indicators portal.

    Source: https://www.bcr.gob.sv/
    """

    indicator: str = ""
    value: str = ""
    date: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
