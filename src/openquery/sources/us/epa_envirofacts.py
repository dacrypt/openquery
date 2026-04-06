"""EPA Envirofacts environmental facility data source — USA.

Queries the EPA Envirofacts REST API for facility environmental compliance.
Free REST API, no auth, no CAPTCHA.

API: https://enviro.epa.gov/enviro/efservice/
Docs: https://www.epa.gov/enviro/envirofacts-data-service-api
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.epa_envirofacts import EpaEnvirofactsResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

EPA_API_BASE = "https://enviro.epa.gov/enviro/efservice"


@register
class EpaEnvirofactsSource(BaseSource):
    """Query EPA Envirofacts environmental facility compliance data."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.epa_envirofacts",
            display_name="EPA Envirofacts — Environmental Facility Data",
            description=(
                "US EPA Envirofacts: environmental compliance, violations, and facility "
                "data by facility name or ZIP code"
            ),
            country="US",
            url="https://enviro.epa.gov/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("facility_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "us.epa_envirofacts",
                "Provide a facility name or ZIP (extra.facility_name or document_number)",
            )
        return self._fetch(search_term)

    def _fetch(self, search_term: str) -> EpaEnvirofactsResult:
        try:
            logger.info("Querying EPA Envirofacts: search_term=%s", search_term)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }

            # Query the ECHO (Enforcement and Compliance History Online) facility endpoint
            url = f"{EPA_API_BASE}/ECHO_EXPORTER/FAC_NAME/CONTAINING/{search_term}/JSON"

            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()

            facility_name = ""
            compliance_status = ""
            violations: list[str] = []

            records = data if isinstance(data, list) else data.get("Results", [])

            if records:
                first = records[0] if isinstance(records[0], dict) else {}
                facility_name = (
                    first.get("FAC_NAME", "")
                    or first.get("facilityName", "")
                    or first.get("name", "")
                )
                compliance_status = (
                    first.get("FAC_COMPLIANCE_STATUS", "")
                    or first.get("complianceStatus", "")
                )
                # Collect any violation descriptions from all records
                for record in records[:10]:
                    if isinstance(record, dict):
                        viol = record.get("FAC_VIOLATION_STATUS", "") or record.get("violation", "")
                        if viol and viol not in violations:
                            violations.append(str(viol))

            return EpaEnvirofactsResult(
                queried_at=datetime.now(),
                search_term=search_term,
                facility_name=facility_name,
                compliance_status=compliance_status,
                violations=violations[:10],
                details=f"EPA Envirofacts query for: {search_term} — {len(records)} records",
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "us.epa_envirofacts", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("us.epa_envirofacts", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("us.epa_envirofacts", f"Query failed: {e}") from e
