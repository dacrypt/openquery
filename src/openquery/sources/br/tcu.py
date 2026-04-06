"""Brazil TCU source — government audit sanctions (licitantes inidôneos).

Queries the TCU (Tribunal de Contas da União) API for companies/individuals
declared ineligible for government contracting.

API: https://inidoneidade.tcu.gov.br/api/ (public REST API)
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.tcu import BrTcuResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

TCU_API_URL = "https://inidoneidade.tcu.gov.br/api/licitante"


@register
class BrTcuSource(BaseSource):
    """Query TCU inidoneidade (government sanctions) by company name or CNPJ."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.tcu",
            display_name="TCU — Licitantes Inidôneos (Sanções a Empresas)",
            description="TCU government sanctions registry — companies/persons ineligible for contracts",  # noqa: E501
            country="BR",
            url="https://inidoneidade.tcu.gov.br/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search = (
            input.extra.get("name", "")
            or input.extra.get("cnpj", "")
            or input.document_number
        ).strip()
        if not search:
            raise SourceError("br.tcu", "Company name or CNPJ is required")
        return self._query(search)

    def _query(self, search: str) -> BrTcuResult:
        try:
            logger.info("Querying TCU sanctions: %s", search)
            params: dict[str, str] = {"search": search, "size": "10", "page": "0"}
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/1.0)",
                "Accept": "application/json",
            }
            with httpx.Client(timeout=self._timeout, headers=headers, follow_redirects=True) as client:  # noqa: E501
                resp = client.get(TCU_API_URL, params=params)
                if resp.status_code in (404, 422):
                    return BrTcuResult(
                        queried_at=datetime.now(),
                        search_term=search,
                        sanction_status="not_found",
                        details={"message": "No sanctions found"},
                    )
                resp.raise_for_status()
                data = resp.json()

            return self._parse_response(data, search)

        except httpx.HTTPStatusError as e:
            raise SourceError("br.tcu", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("br.tcu", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("br.tcu", f"Query failed: {e}") from e

    def _parse_response(self, data: dict | list, search: str) -> BrTcuResult:
        # The API may return a list or a paginated dict
        items: list = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("content", data.get("data", data.get("items", [])))

        if not items:
            return BrTcuResult(
                queried_at=datetime.now(),
                search_term=search,
                sanction_status="clear",
                details={"message": "No active sanctions found", "total": 0},
            )

        first = items[0] if isinstance(items[0], dict) else {}
        company_name = (
            first.get("nome", "")
            or first.get("nomeRazaoSocial", "")
            or first.get("razaoSocial", "")
        )
        cnpj = first.get("cpfCnpj", first.get("cnpj", first.get("cpf", "")))
        status = first.get("situacao", first.get("status", "ineligible"))

        return BrTcuResult(
            queried_at=datetime.now(),
            search_term=search,
            company_name=company_name,
            cnpj=cnpj,
            sanction_status=str(status),
            details={"total_results": len(items), "first_record": first},
        )
