"""CURP source — Mexican population registry (RENAPO).

Queries the Mexican CURP validation system via JSON API.
No browser or CAPTCHA required.

API: https://www.gob.mx/v1/renapoCURP/consulta
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.curp import CurpResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.gob.mx/v1/renapoCURP/consulta"
PAGE_URL = "https://www.gob.mx/curp/"


@register
class CurpSource(BaseSource):
    """Query Mexican CURP population registry via JSON API."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.curp",
            display_name="CURP — Consulta de CURP",
            description="Mexican CURP validation: personal data and birth certificate status",
            country="MX",
            url=PAGE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        curp = input.extra.get("curp", "") or input.document_number
        if not curp:
            raise SourceError("mx.curp", "CURP is required (pass via extra.curp)")
        return self._query(curp.upper().strip())

    def _query(self, curp: str) -> CurpResult:
        try:
            headers = {
                "Content-Type": "application/json",
                "Referer": "https://www.gob.mx/",
                "Origin": "https://www.gob.mx",
            }
            payload = {"curp": curp, "tipoBusqueda": "curp"}

            logger.info("Querying CURP API for: %s", curp)

            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.post(API_URL, json=payload)
                resp.raise_for_status()
                data = resp.json()

            if data.get("codigo") != "01" or not data.get("registros"):
                return CurpResult(
                    queried_at=datetime.now(),
                    curp=curp,
                    estatus="No encontrado",
                )

            registro = data["registros"][0]

            return CurpResult(
                queried_at=datetime.now(),
                curp=registro.get("curp", curp),
                nombre=registro.get("nombres", ""),
                apellido_paterno=registro.get("apellido1", ""),
                apellido_materno=registro.get("apellido2", ""),
                fecha_nacimiento=registro.get("fechNac", ""),
                sexo=registro.get("sexo", ""),
                estado_nacimiento=registro.get("desEntNac", ""),
                estatus=registro.get("statusCurp", ""),
                documento_probatorio=registro.get("docProbatorio", ""),
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("mx.curp", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("mx.curp", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("mx.curp", f"Query failed: {e}") from e
