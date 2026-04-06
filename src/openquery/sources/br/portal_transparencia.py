"""Brazil Portal da Transparência source.

Queries the federal transparency portal API for government employees,
sanctioned companies, and social benefit recipients.

API: https://api.portaldatransparencia.gov.br/
Requires a free API key registered at portaldatransparencia.gov.br.
Set via env: OPENQUERY_BR_TRANSPARENCIA_API_KEY
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.config import get_settings
from openquery.exceptions import SourceError
from openquery.models.br.portal_transparencia import (
    BrPortalTransparenciaResult,
    TransparenciaRecord,
)
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

TRANSPARENCIA_BASE_URL = "https://api.portaldatransparencia.gov.br/api-de-dados"


@register
class BrPortalTransparenciaSource(BaseSource):
    """Query Brazil's federal transparency portal for employees, sanctions, and benefits."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.portal_transparencia",
            display_name="Portal da Transparência — Governo Federal",
            description="Brazil federal transparency: government employees, sanctioned companies, Bolsa Família",  # noqa: E501
            country="BR",
            url="https://portaldatransparencia.gov.br/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        settings = get_settings()
        api_key = getattr(settings, "br_transparencia_api_key", "")

        search_term = (input.extra.get("name", "") or input.document_number).strip()
        search_type = input.extra.get("search_type", "servidores").strip()

        if not search_term:
            raise SourceError(
                "br.portal_transparencia",
                "Provide a name or document number to search",
            )

        if search_type not in ("servidores", "ceis", "bolsa-familia"):
            raise SourceError(
                "br.portal_transparencia",
                "search_type must be one of: servidores, ceis, bolsa-familia",
            )

        return self._search(search_term, search_type, api_key)

    def _search(
        self, search_term: str, search_type: str, api_key: str
    ) -> BrPortalTransparenciaResult:
        try:
            logger.info("Querying Portal Transparência (%s): %s", search_type, search_term)

            headers: dict[str, str] = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }
            if api_key:
                headers["chave-api-dados"] = api_key

            endpoint_map = {
                "servidores": f"{TRANSPARENCIA_BASE_URL}/servidores",
                "ceis": f"{TRANSPARENCIA_BASE_URL}/ceis",
                "bolsa-familia": f"{TRANSPARENCIA_BASE_URL}/bolsa-familia-por-municipio",
            }
            url = endpoint_map[search_type]

            params: dict[str, str | int] = {"pagina": 1}
            # Parameter name depends on endpoint
            if search_type == "servidores":
                params["nome"] = search_term
            elif search_type == "ceis":
                params["cpfCnpj"] = search_term
            else:
                params["mesAno"] = search_term

            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

            records: list[TransparenciaRecord] = []
            raw_records = data if isinstance(data, list) else data.get("data", [])

            for item in raw_records[:10]:
                rec = TransparenciaRecord(
                    nome=item.get("nome", "") or item.get("nomeRazaoSocial", ""),
                    cpf_cnpj=item.get("cpf", "") or item.get("cnpj", ""),
                    orgao=item.get("orgao", {}).get("nome", "")
                    if isinstance(item.get("orgao"), dict)
                    else str(item.get("orgao", "")),
                    cargo=item.get("cargo", {}).get("nome", "")
                    if isinstance(item.get("cargo"), dict)
                    else str(item.get("cargo", "")),
                    valor=str(
                        item.get("remuneracaoBasicaBruta", "") or item.get("valorPago", "") or ""
                    ),
                    details=str(
                        item.get("situacaoVinculo", "") or item.get("fundamentoLegal", "") or ""
                    ),
                )
                records.append(rec)

            return BrPortalTransparenciaResult(
                search_term=search_term,
                search_type=search_type,
                results_count=len(records),
                records=records,
                details=f"Endpoint: {search_type}; {len(records)} records returned",
            )

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 401:
                raise SourceError(
                    "br.portal_transparencia",
                    "API key required or invalid — set OPENQUERY_BR_TRANSPARENCIA_API_KEY",
                ) from e
            raise SourceError("br.portal_transparencia", f"API returned HTTP {status}") from e
        except httpx.RequestError as e:
            raise SourceError("br.portal_transparencia", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("br.portal_transparencia", f"Query failed: {e}") from e
