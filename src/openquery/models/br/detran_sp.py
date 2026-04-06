"""Brazil DETRAN-SP data model — São Paulo vehicle debt lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DetranSpResult(BaseModel):
    """São Paulo DETRAN vehicle debt lookup result.

    Source: https://www.detran.sp.gov.br/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    renavam: str = ""
    vehicle_description: str = ""
    ipva_status: str = ""
    licensing_status: str = ""
    fines_count: int = 0
    total_debt: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
