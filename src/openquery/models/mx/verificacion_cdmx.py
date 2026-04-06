"""VerificacionCdmx data model — CDMX emissions verification status."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VerificacionCdmxResult(BaseModel):
    """Emissions verification status from CDMX SEDEMA portal.

    Source: https://sedema.cdmx.gob.mx/programas/programa/verificacion-vehicular
    """

    placa: str = ""
    hologram_type: str = ""  # "00", "0", "1", "2"
    exemption_status: str = ""
    validity_semester: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
