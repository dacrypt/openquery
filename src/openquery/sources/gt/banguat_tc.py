"""Banguat TC source — Guatemala exchange rates by date.

Queries Banguat (Banco de Guatemala) SOAP web service for the
GTQ/USD exchange rate on a specific date.

API: https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx
URL: https://www.banguat.gob.gt/tipo_cambio/
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.gt.banguat_tc import GtBanguatTcResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

BANGUAT_TC_URL = "https://www.banguat.gob.gt/tipo_cambio/"
BANGUAT_WS_URL = "https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx"

SOAP_BODY_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <TipoCambioFecha xmlns="http://www.banguat.gob.gt/variables/ws/">
      <fechainit>{date}</fechainit>
      <fechafin>{date}</fechafin>
    </TipoCambioFecha>
  </soap:Body>
</soap:Envelope>"""


@register
class GtBanguatTcSource(BaseSource):
    """Query Guatemala Banguat GTQ/USD exchange rate for a specific date."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="gt.banguat_tc",
            display_name="Banguat — Tipo de Cambio por Fecha (GT)",
            description="Guatemala Banguat GTQ/USD exchange rate for a specific date",
            country="GT",
            url=BANGUAT_TC_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        date = input.extra.get("date", "") or input.document_number
        if not date:
            # Default to today
            date = datetime.now().strftime("%d/%m/%Y")
        return self._query(date.strip())

    def _query(self, date: str) -> GtBanguatTcResult:
        try:
            headers = {
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": "http://www.banguat.gob.gt/variables/ws/TipoCambioFecha",
            }
            soap_body = SOAP_BODY_TEMPLATE.format(date=date)
            logger.info("Querying Banguat TC for date: %s", date)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(BANGUAT_WS_URL, content=soap_body, headers=headers)
                resp.raise_for_status()

            root = ET.fromstring(resp.text)
            usd_rate = ""
            fecha = ""
            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag == "fecha" and elem.text:
                    fecha = elem.text.strip()
                elif tag == "referencia" and elem.text:
                    usd_rate = elem.text.strip()

            return GtBanguatTcResult(
                queried_at=datetime.now(),
                date=fecha or date,
                usd_rate=usd_rate,
                details={"moneda": "USD/GTQ", "fecha_consultada": date},
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("gt.banguat_tc", f"HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("gt.banguat_tc", f"Request failed: {e}") from e
        except ET.ParseError as e:
            raise SourceError("gt.banguat_tc", f"Failed to parse SOAP XML: {e}") from e
        except Exception as e:
            raise SourceError("gt.banguat_tc", f"Query failed: {e}") from e
