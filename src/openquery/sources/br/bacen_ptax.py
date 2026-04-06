"""Brazil BACEN PTAX source — USD/BRL exchange rates from Banco Central do Brasil.

Free REST API (OData), no auth, no CAPTCHA.

API: https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/CotacaoDolarDia(dataCotacao=@dataCotacao)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.bacen_ptax import BrBacenPtaxResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

PTAX_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
    "CotacaoDolarDia(dataCotacao=@dataCotacao)"
)


@register
class BrBacenPtaxSource(BaseSource):
    """Query BACEN PTAX USD/BRL daily exchange rates."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.bacen_ptax",
            display_name="BACEN PTAX — Cotação do Dólar (USD/BRL)",
            description="Banco Central do Brasil PTAX daily USD/BRL exchange rates (free OData API)",  # noqa: E501
            country="BR",
            url="https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        date_str = (input.extra.get("date", "") or input.document_number).strip()
        if not date_str:
            # Default to yesterday (BACEN publishes end-of-day rates)
            yesterday = datetime.now() - timedelta(days=1)
            date_str = yesterday.strftime("%m-%d-%Y")
        else:
            # Accept YYYY-MM-DD or MM-DD-YYYY
            date_str = self._normalize_date(date_str)
        return self._query(date_str)

    def _normalize_date(self, date_str: str) -> str:
        """Normalize date to MM-DD-YYYY format expected by BACEN API."""
        # Accept YYYY-MM-DD
        if len(date_str) == 10 and date_str[4] == "-":
            parts = date_str.split("-")
            return f"{parts[1]}-{parts[2]}-{parts[0]}"
        # Already MM-DD-YYYY
        return date_str

    def _query(self, date_mm_dd_yyyy: str) -> BrBacenPtaxResult:
        try:
            logger.info("Querying BACEN PTAX for date: %s", date_mm_dd_yyyy)
            params = {
                "@dataCotacao": f"'{date_mm_dd_yyyy}'",
                "$format": "json",
                "$select": "cotacaoCompra,cotacaoVenda,dataHoraCotacao",
            }
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(PTAX_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            values = data.get("value", [])
            if not values:
                return BrBacenPtaxResult(
                    queried_at=datetime.now(),
                    date=date_mm_dd_yyyy,
                    details={"message": "No rate found for this date (weekend or holiday?)"},
                )

            latest = values[-1]
            buy = latest.get("cotacaoCompra")
            sell = latest.get("cotacaoVenda")
            timestamp = latest.get("dataHoraCotacao", "")

            return BrBacenPtaxResult(
                queried_at=datetime.now(),
                date=date_mm_dd_yyyy,
                buy_rate=float(buy) if buy is not None else None,
                sell_rate=float(sell) if sell is not None else None,
                details={"timestamp": timestamp, "total_quotes": len(values)},
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("br.bacen_ptax", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("br.bacen_ptax", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("br.bacen_ptax", f"Query failed: {e}") from e
