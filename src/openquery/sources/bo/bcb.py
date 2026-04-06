"""BCB central bank exchange rates source — Bolivia.

Queries BCB for current BOB/USD exchange rate.

URL: https://www.bcb.gob.bo/
Input: none (returns current rates)
Returns: USD rate, date
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.bo.bcb import BcbResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

BCB_API_URL = "https://www.bcb.gob.bo/librerias/indicadores/tasas/getTasas.php"


@register
class BcbSource(BaseSource):
    """Query BCB for current exchange rates."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="bo.bcb",
            display_name="BCB — Banco Central de Bolivia (Tipo de Cambio)",
            description="Bolivia BCB central bank: current BOB/USD exchange rate",
            country="BO",
            url="https://www.bcb.gob.bo/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        return self._fetch()

    def _fetch(self) -> BcbResult:
        try:
            logger.info("Querying BCB exchange rates")
            headers = {"User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)"}
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(BCB_API_URL)
                resp.raise_for_status()
                data = resp.json()

            usd_rate = ""
            date = ""

            if isinstance(data, list):
                for item in data:
                    moneda = item.get("moneda", "") or item.get("currency", "")
                    if "USD" in str(moneda).upper() or "DÓLAR" in str(moneda).upper():
                        usd_rate = str(item.get("compra", item.get("venta", item.get("rate", ""))))
                        date = str(item.get("fecha", item.get("date", datetime.now().strftime("%Y-%m-%d"))))  # noqa: E501
                        break
            elif isinstance(data, dict):
                usd_rate = str(data.get("usd", data.get("USD", data.get("compra", ""))))
                date = str(data.get("fecha", data.get("date", datetime.now().strftime("%Y-%m-%d"))))

            return BcbResult(
                queried_at=datetime.now(),
                usd_rate=usd_rate,
                date=date,
                details=f"BCB exchange rate: 1 USD = {usd_rate} BOB",
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("bo.bcb", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("bo.bcb", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("bo.bcb", f"Query failed: {e}") from e
