"""MinSalud data model — Colombian health provider registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MinsaludResult(BaseModel):
    """MinSalud health provider/IPS/EPS habilitacion registry.

    Source: https://prestadores.minsalud.gov.co/habilitacion/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    provider_name: str = ""
    provider_type: str = ""
    habilitacion_status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
