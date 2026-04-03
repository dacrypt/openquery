"""Guatemala Banguat source — exchange rates.

Queries Banguat (Banco de Guatemala) for USD/GTQ exchange rates.
SOAP web service, no auth, no CAPTCHA.

API: https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.gt.banguat import GtBanguatResult, TipoCambio
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

BANGUAT_URL = "https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx"

SOAP_BODY = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <TipoCambioDia xmlns="http://www.banguat.gob.gt/variables/ws/" />
  </soap:Body>
</soap:Envelope>"""


@register
class GtBanguatSource(BaseSource):
    """Query Guatemalan exchange rates (Banguat — Banco de Guatemala)."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="gt.banguat",
            display_name="Banguat — Tipo de Cambio",
            description="Guatemala USD/GTQ exchange rate (Banco de Guatemala / Banguat)",
            country="GT",
            url="https://www.banguat.gob.gt/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        return self._query()

    def _query(self) -> GtBanguatResult:
        try:
            headers = {
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": "http://www.banguat.gob.gt/variables/ws/TipoCambioDia",
            }

            logger.info("Querying Banguat exchange rate")
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(BANGUAT_URL, content=SOAP_BODY, headers=headers)
                resp.raise_for_status()

            # Parse SOAP XML response
            root = ET.fromstring(resp.text)

            registros = []
            for var in root.iter():
                if var.tag.endswith("Var") or "CambioDelDia" in var.tag:
                    fecha = ""
                    ref = ""
                    for child in var:
                        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                        if tag == "fecha" and child.text:
                            fecha = child.text.strip()
                        elif tag == "referencia" and child.text:
                            ref = child.text.strip()
                    if fecha and ref:
                        registros.append(TipoCambio(fecha=fecha, referencia=ref))

            return GtBanguatResult(
                queried_at=datetime.now(),
                moneda="USD/GTQ",
                tipo_cambio=registros[0].referencia if registros else "",
                fecha=registros[0].fecha if registros else "",
                total_registros=len(registros),
                registros=registros,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("gt.banguat", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("gt.banguat", f"Request failed: {e}") from e
        except ET.ParseError as e:
            raise SourceError("gt.banguat", f"Failed to parse SOAP XML: {e}") from e
        except Exception as e:
            raise SourceError("gt.banguat", f"Query failed: {e}") from e
