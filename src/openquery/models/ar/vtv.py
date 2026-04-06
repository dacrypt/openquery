"""VTV data model — Buenos Aires Province vehicle technical inspection."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VtvResult(BaseModel):
    """VTV inspection result for Buenos Aires Province.

    Source: https://vtv.gba.gob.ar/consultar-vtv
    """

    placa: str = ""
    vtv_status: str = ""
    expiration_date: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
