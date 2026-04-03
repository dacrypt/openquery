"""Panama RUC source — DGI (Dirección General de Ingresos) taxpayer lookup.

Queries Panama's DGI CCIC list for taxpayer compliance status.
Simple HTTP POST to PHP form — no browser needed, no CAPTCHA.

Source: https://dgi.mef.gob.pa/CCIC/Lis-CC.php
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pa.ruc import PaRucResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DGI_URL = "https://dgi.mef.gob.pa/CCIC/Lis-CC.php"


@register
class PaRucSource(BaseSource):
    """Query Panamanian DGI taxpayer compliance by RUC or name."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pa.ruc",
            display_name="DGI — Consulta RUC / CCIC",
            description="Panamanian taxpayer compliance status (Dirección General de Ingresos CCIC)",
            country="PA",
            url=DGI_URL,
            supported_inputs=[DocumentType.NIT, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        ruc = input.extra.get("ruc", "") or input.document_number
        name = input.extra.get("name", "")
        if not ruc and not name:
            raise SourceError("pa.ruc", "RUC or name (extra.name) is required")
        return self._query(ruc=ruc.strip(), name=name.strip())

    def _query(self, ruc: str = "", name: str = "") -> PaRucResult:
        try:
            data = {"submit": "BUSCAR"}
            if ruc:
                data["ruc"] = ruc
                data["nombre"] = ""
                logger.info("Querying DGI Panama by RUC: %s", ruc)
            else:
                data["ruc"] = ""
                data["nombre"] = name
                logger.info("Querying DGI Panama by name: %s", name)

            with httpx.Client(timeout=self._timeout, verify=False, follow_redirects=True) as client:
                resp = client.post(DGI_URL, data=data)
                resp.raise_for_status()
                html = resp.text

            return self._parse_html(html, ruc or name)

        except httpx.HTTPStatusError as e:
            raise SourceError("pa.ruc", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("pa.ruc", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("pa.ruc", f"Query failed: {e}") from e

    def _parse_html(self, html: str, query: str) -> PaRucResult:
        result = PaRucResult(queried_at=datetime.now(), ruc=query)

        # Extract table rows from HTML response
        # The CCIC page returns an HTML table with taxpayer data
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE)

        for row in rows:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
            cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
            if len(cells) >= 2 and cells[0]:
                # First meaningful data row
                if not result.nombre:
                    result.ruc = cells[0] if len(cells) > 0 else ""
                    result.nombre = cells[1] if len(cells) > 1 else ""
                    result.estado = cells[2] if len(cells) > 2 else ""

        if not result.nombre and "No se encontraron" in html:
            result.mensaje = "No se encontraron resultados"
        elif result.nombre:
            result.mensaje = f"Contribuyente encontrado: {result.nombre}"

        return result
