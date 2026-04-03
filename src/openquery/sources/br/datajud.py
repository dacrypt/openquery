"""Brazil DataJud source — CNJ judicial process lookup.

Queries the DataJud public API (CNJ) for judicial processes.
Free REST API with public API key, no CAPTCHA.

API: https://api-publica.datajud.cnj.jus.br/
Docs: https://datajud-wiki.cnj.jus.br/api-publica/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.datajud import BrDatajudResult, MovimentoProcessual
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

# Public API key (published on DataJud wiki)
API_KEY = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="
API_BASE = "https://api-publica.datajud.cnj.jus.br"
DEFAULT_COURT = "api_publica_tjsp"


@register
class BrDatajudSource(BaseSource):
    """Query Brazilian judicial processes via DataJud/CNJ API."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.datajud",
            display_name="DataJud — Consulta Processual (CNJ)",
            description="Brazilian judicial process lookup via CNJ DataJud public API",
            country="BR",
            url="https://datajud-wiki.cnj.jus.br/api-publica/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        numero = input.extra.get("processo", "") or input.document_number
        court = input.extra.get("tribunal", DEFAULT_COURT)
        if not numero:
            raise SourceError("br.datajud", "Processo number is required")
        return self._query(numero.strip(), court)

    def _query(self, numero: str, court: str) -> BrDatajudResult:
        try:
            url = f"{API_BASE}/{court}/_search"
            headers = {
                "Authorization": f"APIKey {API_KEY}",
                "Content-Type": "application/json",
            }
            body = {
                "query": {
                    "match": {
                        "numeroProcesso": numero,
                    }
                },
                "size": 10,
            }

            logger.info("Querying DataJud %s for processo: %s", court, numero)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(url, json=body, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            hits = data.get("hits", {}).get("hits", [])
            total = data.get("hits", {}).get("total", {}).get("value", 0)

            if not hits:
                return BrDatajudResult(
                    queried_at=datetime.now(),
                    numero_processo=numero,
                    tribunal=court,
                    total_resultados=0,
                )

            src = hits[0].get("_source", {})

            # Parse movements
            movimentos = []
            for m in src.get("movimentos", [])[:20]:
                movimentos.append(MovimentoProcessual(
                    data=m.get("dataHora", ""),
                    nome=m.get("nome", ""),
                    complemento=", ".join(
                        c.get("nome", "") for c in m.get("complementosTabelados", [])
                    ),
                ))

            # Parse subjects
            assuntos = [a.get("nome", "") for a in src.get("assuntos", []) if a.get("nome")]

            return BrDatajudResult(
                queried_at=datetime.now(),
                numero_processo=src.get("numeroProcesso", numero),
                classe=src.get("classe", {}).get("nome", "") if isinstance(src.get("classe"), dict) else str(src.get("classe", "")),
                sistema=src.get("siglaSistema", ""),
                orgao_julgador=src.get("orgaoJulgador", {}).get("nome", "") if isinstance(src.get("orgaoJulgador"), dict) else "",
                tribunal=src.get("tribunal", court),
                data_ajuizamento=src.get("dataAjuizamento", ""),
                assuntos=assuntos,
                movimentos=movimentos,
                total_movimentos=len(movimentos),
                total_resultados=total,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("br.datajud", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("br.datajud", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("br.datajud", f"Query failed: {e}") from e
