"""Nicaragua BCN source — exchange rates (HTML scrape).

Scrapes the official BCN (Banco Central de Nicaragua) page for the current
NIO/USD official exchange rate. No auth, no CAPTCHA.

Source: https://www.bcn.gob.ni/estadisticas/mercados_cambiarios/tipo_cambio/cordoba_dolar/
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ni.bcn import NiBcnResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

BCN_URL = (
    "https://www.bcn.gob.ni/estadisticas/mercados_cambiarios/tipo_cambio/cordoba_dolar/"
)


@register
class NiBcnSource(BaseSource):
    """Query Nicaragua BCN official NIO/USD exchange rate."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ni.bcn",
            display_name="BCN — Tipo de Cambio NIO/USD",
            description=(
                "Nicaragua Central Bank official NIO/USD exchange rate "
                "(Banco Central de Nicaragua)"
            ),
            country="NI",
            url="https://www.bcn.gob.ni/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        return self._query()

    def _query(self) -> NiBcnResult:
        try:
            logger.info("Querying BCN Nicaragua exchange rate")
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "es-NI,es;q=0.9,en;q=0.8",
            }
            with httpx.Client(
                timeout=self._timeout, headers=headers, follow_redirects=True
            ) as client:
                resp = client.get(BCN_URL)
                resp.raise_for_status()
                html = resp.text

            return self._parse_html(html)

        except httpx.HTTPStatusError as e:
            raise SourceError("ni.bcn", f"HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("ni.bcn", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("ni.bcn", f"Query failed: {e}") from e

    def _parse_html(self, html: str) -> NiBcnResult:
        """Parse BCN HTML for NIO/USD exchange rate."""
        details: dict[str, str] = {}

        usd_rate = ""
        # BCN typically shows the rate as a decimal number after "Dólar" or "USD"
        rate_pattern = re.compile(
            r"(?:D[oó]lar|USD|C\$|NIO).*?(\d{1,3}[.,]\d{1,6})",
            re.DOTALL | re.IGNORECASE,
        )
        m = rate_pattern.search(html)
        if m:
            usd_rate = m.group(1).strip()
            details["USD"] = usd_rate
            logger.debug("BCN NIO/USD rate: %s", usd_rate)

        # Fallback: look for a standalone decimal number in the 35–40 range (typical NIO/USD)
        if not usd_rate:
            fallback = re.compile(r"\b(3\d\.\d{4,6})\b")
            fm = fallback.search(html)
            if fm:
                usd_rate = fm.group(1).strip()
                details["USD"] = usd_rate

        # Extract date
        date_str = ""
        date_pattern = re.compile(
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+de\s+\w+\s+de\s+\d{4})",
            re.IGNORECASE,
        )
        dm = date_pattern.search(html)
        if dm:
            date_str = dm.group(1).strip()
            details["fecha"] = date_str

        return NiBcnResult(
            queried_at=datetime.now(),
            usd_rate=usd_rate,
            date=date_str,
            details=details,
        )
