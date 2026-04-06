"""SAIME data model — Venezuela identity/cedula filiatory data."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SaimeResult(BaseModel):
    """Venezuela SAIME cedula filiatory data lookup result.

    Source: https://datosfiliatorios.saime.gob.ve/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    nombre: str = ""
    document_status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
