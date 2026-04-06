"""El Salvador vehicle registry data model — SERTRACEN."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SvVehiculoResult(BaseModel):
    """El Salvador vehicle registry (SERTRACEN) lookup result.

    Source: https://www.sertracen.com.sv/index.php/consultas-en-linea-del-registro-publico-de-vehiculos/consulta-de-estado-de-vehiculos
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_value: str = ""
    vehicle_status: str = ""
    registration_status: str = ""
    liens: list[str] = Field(default_factory=list)
    owner: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
