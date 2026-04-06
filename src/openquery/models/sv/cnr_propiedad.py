"""El Salvador CNR property registry model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CnrPropiedadResult(BaseModel):
    """CNR property registry result for El Salvador.

    Source: https://www.e.cnr.gob.sv/ServiciosOL/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_value: str = ""
    owner: str = ""
    property_status: str = ""
    liens: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
