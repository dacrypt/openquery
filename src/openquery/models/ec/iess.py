"""IESS data model — Ecuador social security affiliation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IessResult(BaseModel):
    """Affiliation status from Ecuador's Instituto Ecuatoriano de Seguridad Social.

    Source: https://www.iess.gob.ec/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    affiliation_status: str = ""
    employer: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
