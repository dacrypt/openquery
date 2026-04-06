"""BCH source — Honduras Central Bank exchange rates.

Queries Honduras BCH (Banco Central de Honduras) for the
current HNL/USD exchange rate. API-based, no CAPTCHA.

URL: https://www.bch.hn/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.hn.bch import HnBchResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

BCH_URL = "https://www.bch.hn/"
BCH_API_URL = "https://www.bch.hn/estadisticos/EMN/tasa_cambio_referencial.htm"


@register
class HnBchSource(BaseSource):
    """Query Honduras BCH HNL/USD exchange rate."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="hn.bch",
            display_name="BCH — Tasa de Cambio (HN)",
            description="Honduras BCH (Banco Central) HNL/USD exchange rate",
            country="HN",
            url=BCH_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        return self._query()

    def _query(self) -> HnBchResult:
        try:
            logger.info("Querying BCH HNL/USD exchange rate")
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "es-HN,es;q=0.9,en;q=0.8",
            }
            with httpx.Client(
                timeout=self._timeout, headers=headers, follow_redirects=True
            ) as client:
                resp = client.get(BCH_API_URL)
                resp.raise_for_status()
                html = resp.text

            return self._parse_html(html)

        except httpx.HTTPStatusError as e:
            raise SourceError("hn.bch", f"HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("hn.bch", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("hn.bch", f"Query failed: {e}") from e

    def _parse_html(self, html: str) -> HnBchResult:
        import re

        usd_rate = ""
        date_str = ""

        # Look for HNL/USD rate patterns — typically a decimal number like 24.6982
        rate_pattern = re.compile(
            r"(?:USD|dólar|d[oó]lares?|tasa).*?(\d{2,3}[.,]\d{2,6})",
            re.IGNORECASE | re.DOTALL,
        )
        m = rate_pattern.search(html)
        if m:
            usd_rate = m.group(1).strip()

        # Fallback: find any decimal number in range 20-30 (typical HNL/USD range)
        if not usd_rate:
            fallback = re.compile(r"\b(2\d\.\d{4,6})\b")
            fm = fallback.search(html)
            if fm:
                usd_rate = fm.group(1).strip()

        # Extract date
        date_pattern = re.compile(
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+de\s+\w+\s+de\s+\d{4})",
            re.IGNORECASE,
        )
        dm = date_pattern.search(html)
        if dm:
            date_str = dm.group(1).strip()

        return HnBchResult(
            queried_at=datetime.now(),
            usd_rate=usd_rate,
            date=date_str,
            details={"moneda": "HNL/USD"},
        )
