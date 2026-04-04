"""Interpol Red Notices source — wanted persons lookup.

Queries Interpol's public Red Notices API for persons wanted internationally.
Free REST API, no auth, no CAPTCHA. Rate limit: 1000 req/hour.

API: https://ws-public.interpol.int/notices/v1/red
Docs: https://interpol.api.bund.dev/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.interpol import IntlInterpolResult, InterpolNotice
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://ws-public.interpol.int/notices/v1/red"


@register
class InterpolSource(BaseSource):
    """Search Interpol Red Notices for wanted persons."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.interpol",
            display_name="Interpol — Red Notices (Personas Buscadas)",
            description="Interpol Red Notices: internationally wanted persons search (free public API)",
            country="INTL",
            url="https://www.interpol.int/en/How-we-work/Notices/Red-Notices",
            supported_inputs=[DocumentType.CEDULA, DocumentType.PASSPORT, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=60,
        )

    def query(self, input: QueryInput) -> BaseModel:
        name = input.extra.get("name", "").strip()
        nationality = input.extra.get("nationality", "").strip()
        doc_number = input.document_number.strip()

        if not name and not doc_number:
            raise SourceError("intl.interpol", "Provide a name (extra.name) or document number")

        search_name = name if name else doc_number
        return self._search(search_name, nationality)

    def _search(self, name: str, nationality: str = "") -> IntlInterpolResult:
        try:
            params: dict[str, str] = {"resultPerPage": "20"}

            # Split name into forename/name if space present
            parts = name.split(maxsplit=1)
            if len(parts) == 2:
                params["forename"] = parts[0]
                params["name"] = parts[1]
            else:
                params["name"] = name

            if nationality:
                params["nationality"] = nationality.upper()

            logger.info("Searching Interpol Red Notices: %s", name)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            total = data.get("total", 0)
            embedded = data.get("_embedded", {})
            notices_data = embedded.get("notices", [])

            notices = []
            for n in notices_data:
                nationalities = []
                for nat in n.get("nationalities", []):
                    if isinstance(nat, str):
                        nationalities.append(nat)
                    elif isinstance(nat, dict):
                        nationalities.append(nat.get("code", ""))

                # Extract charge from arrest warrants
                charge = ""
                for aw in n.get("arrest_warrants", []):
                    if aw.get("charge"):
                        charge = aw["charge"][:200]
                        break

                links = n.get("_links", {})
                self_link = links.get("self", {}).get("href", "")

                notices.append(InterpolNotice(
                    entity_id=n.get("entity_id", ""),
                    name=n.get("name", ""),
                    forename=n.get("forename", ""),
                    date_of_birth=n.get("date_of_birth", ""),
                    nationalities=nationalities,
                    sex=n.get("sex_id", ""),
                    charge=charge,
                    issuing_country=n.get("issuing_country_id", ""),
                    url=self_link,
                ))

            return IntlInterpolResult(
                queried_at=datetime.now(),
                query=name,
                total=total,
                notices=notices,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("intl.interpol", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("intl.interpol", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("intl.interpol", f"Query failed: {e}") from e
