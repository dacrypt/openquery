"""INPI data model — Argentine trademark search."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InpiResult(BaseModel):
    """INPI (Instituto Nacional de la Propiedad Industrial) trademark search result.

    Source: https://portaltramites.inpi.gob.ar/marcas_702_702busq.php
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    trademark_name: str = ""
    owner: str = ""
    status: str = ""
    trademark_class: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
