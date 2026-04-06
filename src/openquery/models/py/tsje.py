"""Paraguay TSJE data model — electoral registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PyTsjeResult(BaseModel):
    """Paraguay TSJE electoral registry result.

    Source: https://padron.tsje.gov.py/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    ci: str = ""
    nombre: str = ""
    lugar_votacion: str = ""
    mesa: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
