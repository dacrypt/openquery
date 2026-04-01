"""CUFE DIAN data model — Colombian electronic invoice verification."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CufeDianResult(BaseModel):
    """DIAN electronic invoice (factura electrónica) verification by CUFE.

    Source: https://catalogo-vpfe.dian.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cufe: str = ""
    es_valida: bool = False
    emisor_nit: str = ""
    emisor_nombre: str = ""
    receptor_nit: str = ""
    receptor_nombre: str = ""
    numero_factura: str = ""
    fecha_emision: str = ""
    valor_total: str = ""
    estado: str = ""
    mensaje: str = ""
    audit: Any | None = Field(default=None, exclude=True)
