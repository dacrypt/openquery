"""Brazil taxas source — interest rates (Selic, CDI, IPCA) via BrasilAPI.

Free REST API, no auth, no CAPTCHA.

API: https://brasilapi.com.br/api/taxas/v1
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.taxas import BrTaxasResult, Taxa
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://brasilapi.com.br/api/taxas/v1"


@register
class BrTaxasSource(BaseSource):
    """Query Brazilian interest rates (Selic, CDI, IPCA) via BrasilAPI."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.taxas",
            display_name="Taxas — Selic, CDI, IPCA",
            description="Brazilian interest rates: Selic, CDI, IPCA (BrasilAPI/BACEN)",
            country="BR",
            url="https://brasilapi.com.br/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        return self._query()

    def _query(self) -> BrTaxasResult:
        try:
            logger.info("Querying BrasilAPI taxas")
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL)
                resp.raise_for_status()
                data = resp.json()

            selic = cdi = ipca = 0.0
            taxas = []
            for t in data:
                nome = t.get("nome", "")
                valor = float(t.get("valor", 0) or 0)
                taxas.append(Taxa(nome=nome, valor=valor))
                if "selic" in nome.lower():
                    selic = valor
                elif "cdi" in nome.lower():
                    cdi = valor
                elif "ipca" in nome.lower():
                    ipca = valor

            return BrTaxasResult(
                queried_at=datetime.now(),
                selic=selic,
                cdi=cdi,
                ipca=ipca,
                total=len(taxas),
                taxas=taxas,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("br.taxas", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("br.taxas", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("br.taxas", f"Query failed: {e}") from e
