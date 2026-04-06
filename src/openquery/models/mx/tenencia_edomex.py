"""TenenciaEdomex data model — Estado de Mexico vehicle tax (tenencia)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TenenciaEdomexResult(BaseModel):
    """Vehicle tenencia tax status from Estado de Mexico's SFPYA portal.

    Source: https://sfpya.edomexico.gob.mx/controlv/faces/tramiteselectronicos/cv/portalPublico/ConsultaVigenciaPlaca.xhtml
    """

    placa: str = ""
    tenencia_amount: str = ""
    payment_status: str = ""
    vehicle_description: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
