"""BCV source — Venezuela Central Bank exchange rates.

Scrapes the official BCV exchange rate reference page (no CAPTCHA, no auth).

Flow:
1. Fetch HTML from BCV estadisticas page
2. Parse currency rate blocks (USD, EUR, CNY, TRY, RUB)
3. Return BcvResult with all rates

Source: https://www.bcv.org.ve/estadisticas/tipo-de-cambio-de-referencia
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ve.bcv import BcvResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

BCV_URL = "https://www.bcv.org.ve/estadisticas/tipo-de-cambio-de-referencia"


@register
class BcvSource(BaseSource):
    """Query Venezuela Central Bank official exchange rates."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ve.bcv",
            display_name="BCV — Tipo de Cambio de Referencia",
            description="Venezuela Central Bank official exchange rates (USD, EUR, CNY, TRY, RUB)",
            country="VE",
            url=BCV_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        return self._query()

    def _query(self) -> BcvResult:
        try:
            logger.info("Querying BCV exchange rates")
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "es-VE,es;q=0.9,en;q=0.8",
            }
            with httpx.Client(
                timeout=self._timeout, headers=headers, follow_redirects=True
            ) as client:
                resp = client.get(BCV_URL)
                resp.raise_for_status()
                html = resp.text

            return self._parse_html(html)

        except httpx.HTTPStatusError as e:
            raise SourceError("ve.bcv", f"HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("ve.bcv", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("ve.bcv", f"Query failed: {e}") from e

    def _parse_html(self, html: str) -> BcvResult:
        """Parse BCV HTML for exchange rates."""
        import re

        details: dict[str, str] = {}

        # BCV uses strong tags with currency names and rate values
        # Pattern: currency code block with rate nearby
        currency_map = {
            "USD": "usd_rate",
            "EUR": "eur_rate",
            "CNY": "cny_rate",
            "TRY": "try_rate",
            "RUB": "rub_rate",
        }

        rates: dict[str, str] = {v: "" for v in currency_map.values()}

        # Try to find rate blocks: each currency has a div/strong with code + rate value
        # BCV pattern: <strong>USD</strong> ... <strong>4.123,45</strong> or similar
        for currency, field in currency_map.items():
            # Look for currency code followed by a decimal number within ~300 chars
            pattern = re.compile(
                rf"{currency}.*?(\d{{1,3}}(?:[.,]\d{{3}})*(?:[.,]\d{{1,6}}))",
                re.DOTALL | re.IGNORECASE,
            )
            m = pattern.search(html)
            if m:
                raw = m.group(1).strip()
                rates[field] = raw
                details[currency] = raw
                logger.debug("BCV %s rate: %s", currency, raw)

        # Extract date: look for common date patterns in the page
        date_str = ""
        date_pattern = re.compile(
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+de\s+\w+\s+de\s+\d{4})",
            re.IGNORECASE,
        )
        dm = date_pattern.search(html)
        if dm:
            date_str = dm.group(1).strip()

        return BcvResult(
            queried_at=datetime.now(),
            usd_rate=rates["usd_rate"],
            eur_rate=rates["eur_rate"],
            cny_rate=rates["cny_rate"],
            try_rate=rates["try_rate"],
            rub_rate=rates["rub_rate"],
            date=date_str,
            details=details,
        )
