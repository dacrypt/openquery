"""Panama Contraloria data model — government accountability news/reports."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ContraloriaPost(BaseModel):
    """A Contraloria news post."""

    id: int = 0
    titulo: str = ""
    fecha: str = ""
    extracto: str = ""
    url: str = ""


class PaContraloriaResult(BaseModel):
    """Panama Contraloria news/reports result.

    Source: https://www.contraloria.gob.pa/wp-json/wp/v2/posts
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    total: int = 0
    posts: list[ContraloriaPost] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
