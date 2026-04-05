"""Panama PanamaCompra source — government contracts (OCDS API).

Queries Panama's PanamaCompra en Cifras OCDS v2 API for public contracts.
Free REST API, no auth, no CAPTCHA.

API: https://ocdsv2dev.panamacompraencifras.gob.pa/api
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pa.panamacompra import PanamaCompraContract, PanamaCompraResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_BASE_URL = "https://ocdsv2dev.panamacompraencifras.gob.pa/api"
PAGE_URL = "https://ocdsv2dev.panamacompraencifras.gob.pa/"


@register
class PanamaCompraSource(BaseSource):
    """Query Panama government contracts via PanamaCompra OCDS API."""

    def __init__(self, timeout: float = 20.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pa.panamacompra",
            display_name="PanamaCompra — Contratos de Gobierno",
            description="Panama government contracts from PanamaCompra en Cifras (OCDS API)",
            country="PA",
            url=PAGE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search = (
            input.extra.get("q", "")
            or input.extra.get("supplier", "")
            or input.extra.get("buyer", "")
            or input.document_number
        ).strip()
        if not search:
            raise SourceError(
                "pa.panamacompra",
                "Search term required — use extra['q'], extra['supplier'], extra['buyer'],"
                " or document_number",
            )
        return self._query(search)

    def _query(self, search: str) -> PanamaCompraResult:
        try:
            logger.info("Querying PanamaCompra OCDS API: %s", search)
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                resp = client.get(
                    f"{API_BASE_URL}/ocdsReleasePackages",
                    params={"q": search, "pageSize": 50},
                )
                resp.raise_for_status()
                data = resp.json()

            return self._parse_response(data, search)

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "pa.panamacompra", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("pa.panamacompra", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("pa.panamacompra", f"Query failed: {e}") from e

    def _parse_response(self, data: dict, search: str) -> PanamaCompraResult:
        releases = data.get("releases", [])
        if not releases and "packages" in data:
            # Some OCDS endpoints wrap in packages
            for pkg in data["packages"]:
                releases.extend(pkg.get("releases", []))

        contracts: list[PanamaCompraContract] = []
        for release in releases:
            ocid = release.get("ocid", "")
            date = release.get("date", "")

            # Buyer
            buyer_obj = release.get("buyer", {})
            buyer = buyer_obj.get("name", "") if isinstance(buyer_obj, dict) else ""

            # Tender info
            tender = release.get("tender", {})
            title = tender.get("title", "") if isinstance(tender, dict) else ""
            description = tender.get("description", "") if isinstance(tender, dict) else ""
            status = tender.get("status", "") if isinstance(tender, dict) else ""

            # Value from tender or contracts
            value_str = ""
            currency = ""
            tender_value = tender.get("value", {}) if isinstance(tender, dict) else {}
            if isinstance(tender_value, dict) and tender_value:
                amount = tender_value.get("amount", "")
                currency = tender_value.get("currency", "")
                value_str = str(amount) if amount != "" else ""

            # Supplier from awards
            supplier = ""
            for award in release.get("awards", []):
                if not isinstance(award, dict):
                    continue
                suppliers = award.get("suppliers", [])
                if suppliers and isinstance(suppliers[0], dict):
                    supplier = suppliers[0].get("name", "")
                    break
                # Try award value if tender has none
                if not value_str:
                    award_value = award.get("value", {})
                    if isinstance(award_value, dict):
                        amount = award_value.get("amount", "")
                        currency = award_value.get("currency", currency)
                        value_str = str(amount) if amount != "" else ""

            contracts.append(PanamaCompraContract(
                ocid=ocid,
                title=title,
                description=description,
                status=status,
                value=value_str,
                currency=currency,
                buyer=buyer,
                supplier=supplier,
                date=date,
            ))

        total = data.get("count", data.get("total", len(contracts)))
        return PanamaCompraResult(
            search_term=search,
            total=int(total) if total else len(contracts),
            contracts=contracts,
        )
