"""ANEEL EV charging station source — Brazil EV station registry.

Queries ANEEL's open data portal (CKAN) for registered EV charging
stations in Brazil. Supports filtering by state (UF), city, and operator.
No authentication required.

API: https://dadosabertos.aneel.gov.br/api/3/action/datastore_search
Docs: https://dadosabertos.aneel.gov.br/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.aneel_ev import AneelEvResult, AneelEvStation
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CKAN_BASE = "https://dadosabertos.aneel.gov.br/api/3/action"
PACKAGE_SHOW_URL = f"{CKAN_BASE}/package_show"
DATASTORE_SEARCH_URL = f"{CKAN_BASE}/datastore_search"

# Known resource ID for ANEEL EV charging stations dataset
# Package: infraestrutura-de-recarga-de-veiculos-eletricos
_EV_PACKAGE_ID = "infraestrutura-de-recarga-de-veiculos-eletricos"


@register
class AneelEvSource(BaseSource):
    """Query ANEEL open data for EV charging stations in Brazil."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout
        self._resource_id: str | None = None

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.aneel_ev",
            display_name="ANEEL — Estações de Recarga de Veículos Elétricos (Brasil)",
            description=(
                "ANEEL open data: registered EV charging stations in Brazil. "
                "Filter by state (UF), city, or operator."
            ),
            country="BR",
            url="https://dadosabertos.aneel.gov.br/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        extra = input.extra or {}
        state = extra.get("state", "").strip().upper()
        city = extra.get("city", "").strip()
        operator = extra.get("operator", "").strip()

        return self._fetch(state, city, operator)

    def _get_resource_id(self, client: httpx.Client) -> str:
        """Discover EV dataset resource_id via CKAN package_show."""
        if self._resource_id:
            return self._resource_id

        resp = client.get(PACKAGE_SHOW_URL, params={"id": _EV_PACKAGE_ID})
        resp.raise_for_status()
        pkg = resp.json()

        resources = pkg.get("result", {}).get("resources", [])
        if not resources:
            raise SourceError("br.aneel_ev", "No resources found in ANEEL EV dataset")

        # Prefer resource with datastore (tabular data)
        for res in resources:
            if res.get("datastore_active"):
                self._resource_id = res["id"]
                return self._resource_id

        # Fallback to first resource
        self._resource_id = resources[0]["id"]
        return self._resource_id

    def _fetch(self, state: str, city: str, operator: str) -> AneelEvResult:
        try:
            search_parts = []
            if state:
                search_parts.append(f"state={state}")
            if city:
                search_parts.append(f"city={city}")
            if operator:
                search_parts.append(f"operator={operator}")
            search_str = " ".join(search_parts) if search_parts else "all"

            logger.info("Querying ANEEL EV: %s", search_str)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resource_id = self._get_resource_id(client)

                params: dict[str, str | int] = {
                    "resource_id": resource_id,
                    "limit": 100,
                }

                # Build CKAN filters
                filters: dict[str, str] = {}
                if state:
                    filters["SigUF"] = state
                if city:
                    filters["NomMunicipio"] = city
                if operator:
                    filters["NomEmpresa"] = operator
                if filters:
                    import json
                    params["filters"] = json.dumps(filters)

                resp = client.get(DATASTORE_SEARCH_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            result_data = data.get("result", {}) or {}
            records = result_data.get("records", []) or []
            total = result_data.get("total", len(records))

            stations: list[AneelEvStation] = []
            for rec in records:
                stations.append(
                    AneelEvStation(
                        name=str(rec.get("NomEstacao", "") or ""),
                        operator=str(rec.get("NomEmpresa", "") or ""),
                        address=str(rec.get("DscEndereco", "") or ""),
                        city=str(rec.get("NomMunicipio", "") or ""),
                        state=str(rec.get("SigUF", "") or ""),
                        power_kw=str(rec.get("VlrPotencia", "") or ""),
                        connector_type=str(rec.get("DscConector", "") or ""),
                        public_access=str(rec.get("DscAcessoPublico", "") or ""),
                    )
                )

            logger.info("ANEEL EV returned %d stations for: %s", len(stations), search_str)
            return AneelEvResult(
                queried_at=datetime.now(),
                search_params=search_str,
                total_stations=total,
                stations=stations,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("br.aneel_ev", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("br.aneel_ev", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("br.aneel_ev", f"Query failed: {e}") from e
