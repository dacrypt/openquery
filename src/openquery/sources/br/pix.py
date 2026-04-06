"""Brazil PIX source — PIX payment participants via BrasilAPI.

Lists PIX payment system participants (banks/fintechs). Free REST API.

API: https://brasilapi.com.br/api/pix/v1/participants
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.pix import BrPixResult, PixParticipant
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://brasilapi.com.br/api/pix/v1/participants"


@register
class BrPixSource(BaseSource):
    """Query Brazilian PIX payment participants via BrasilAPI."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.pix",
            display_name="PIX — Participantes do Sistema de Pagamentos",
            description="Brazilian PIX payment system participants (banks, fintechs) via BrasilAPI/BACEN",  # noqa: E501
            country="BR",
            url="https://brasilapi.com.br/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search = input.extra.get("nome", "") or input.document_number
        return self._query(search.strip() if search else "")

    def _query(self, search: str) -> BrPixResult:
        try:
            logger.info("Querying BrasilAPI PIX participants")
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_URL)
                resp.raise_for_status()
                data = resp.json()

            # Filter by name if search term provided
            if search:
                search_lower = search.lower()
                data = [p for p in data if search_lower in p.get("nome", "").lower()]

            participants = []
            for p in data[:50]:
                participants.append(
                    PixParticipant(
                        ispb=str(p.get("ispb", "")),
                        nome=p.get("nome", ""),
                        cnpj=p.get("cnpj", "") or "",
                        tipo_participacao=p.get("tipo_participacao", ""),
                        inicio_operacao=p.get("inicio_operacao", ""),
                    )
                )

            return BrPixResult(
                queried_at=datetime.now(),
                query=search,
                total=len(participants),
                participantes=participants,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("br.pix", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("br.pix", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("br.pix", f"Query failed: {e}") from e
