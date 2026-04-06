"""Brazil TSE candidate/politician lookup source.

Queries the TSE open data API for candidate information including party,
position, election year, and declared assets.

API: https://dadosabertos.tse.jus.br/
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.tse_candidatos import BrTseCandidatosResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

TSE_API_URL = "https://dadosabertos.tse.jus.br/api/3/action/datastore_search"
TSE_CANDIDATOS_RESOURCE = "bbe75dcd-5733-4897-b977-86cf7dfb5126"


@register
class BrTseCandidatosSource(BaseSource):
    """Query Brazil TSE for candidate/politician information."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.tse_candidatos",
            display_name="TSE — Candidatos e Políticos",
            description="Brazil TSE: candidate lookup with party, position, election year, and declared assets",  # noqa: E501
            country="BR",
            url="https://dadosabertos.tse.jus.br/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        name = input.extra.get("name", "").strip()
        cpf = (input.extra.get("cpf", "") or input.document_number).strip()

        if not name and not cpf:
            raise SourceError("br.tse_candidatos", "Provide a candidate name (extra.name) or CPF")

        search_term = name if name else cpf
        return self._search(search_term)

    def _search(self, search_term: str) -> BrTseCandidatosResult:
        try:
            logger.info("Searching TSE candidates: %s", search_term)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }

            params = {
                "resource_id": TSE_CANDIDATOS_RESOURCE,
                "q": search_term,
                "limit": 5,
            }

            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(TSE_API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            result_data = data.get("result", {})
            records = result_data.get("records", [])
            total = result_data.get("total", 0)

            if not records:
                return BrTseCandidatosResult(
                    search_term=search_term,
                    details="No candidates found",
                )

            # Use the first/best match
            rec = records[0]
            candidate_name = rec.get("NM_CANDIDATO", "") or rec.get("NM_UE", "") or ""
            cpf_val = rec.get("NR_CPF_CANDIDATO", "") or rec.get("CPF", "") or ""
            party = rec.get("SG_PARTIDO", "") or rec.get("NM_PARTIDO", "") or ""
            position = rec.get("DS_CARGO", "") or rec.get("NM_CARGO", "") or ""
            election_year = str(rec.get("ANO_ELEICAO", "") or "")
            declared_assets = str(
                rec.get("VR_BEM_CANDIDATO", "") or rec.get("VR_PATRIMONIO", "") or ""
            )

            details_parts = []
            if total > 1:
                details_parts.append(f"{total} candidates found; showing first match")
            for k, v in list(rec.items())[:8]:
                if v and str(v).strip():
                    details_parts.append(f"{k}: {v}")
            details = " | ".join(details_parts[:6])

            return BrTseCandidatosResult(
                search_term=search_term,
                candidate_name=candidate_name,
                cpf=str(cpf_val),
                party=party,
                position=position,
                election_year=election_year,
                declared_assets=declared_assets,
                details=details,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "br.tse_candidatos", f"TSE API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("br.tse_candidatos", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("br.tse_candidatos", f"Query failed: {e}") from e
