"""SAT 69-B Completo data model — Mexican EFOS full list (Mexico)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Sat69bCompletoResult(BaseModel):
    """SAT 69-B full EFOS list with classification (Mexico).

    Source: https://www.sat.gob.mx/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    rfc: str = ""
    taxpayer_name: str = ""
    efos_status: str = ""
    classification: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
