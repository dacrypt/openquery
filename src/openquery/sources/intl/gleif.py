"""GLEIF source — Legal Entity Identifier (LEI) registry lookup.

Queries the GLEIF (Global Legal Entity Identifier Foundation) API for LEI records.
Free REST API, no auth required.

API: https://api.gleif.org/api/v1/lei-records
Docs: https://www.gleif.org/en/lei-data/gleif-api/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.gleif import IntlGleifResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

GLEIF_API_URL = "https://api.gleif.org/api/v1/lei-records"


@register
class IntlGleifSource(BaseSource):
    """Query GLEIF LEI registry by company name or LEI code."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.gleif",
            display_name="GLEIF — Legal Entity Identifier (LEI) Registry",
            description="GLEIF LEI registry: legal entity identifiers, jurisdiction, and entity status",  # noqa: E501
            country="INTL",
            url="https://www.gleif.org/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search = (
            input.extra.get("name", "") or input.extra.get("lei", "") or input.document_number
        ).strip()
        if not search:
            raise SourceError(
                "intl.gleif",
                "Company name or LEI is required (extra['name'] or extra['lei'])",
            )
        # Detect if it looks like a LEI (20-char alphanumeric)
        if len(search) == 20 and search.isalnum():
            return self._query_by_lei(search)
        return self._query_by_name(search)

    def _query_by_lei(self, lei: str) -> IntlGleifResult:
        try:
            logger.info("Querying GLEIF by LEI: %s", lei)
            headers = {"Accept": "application/vnd.api+json"}
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(f"{GLEIF_API_URL}/{lei}")
                if resp.status_code == 404:
                    return IntlGleifResult(
                        queried_at=datetime.now(),
                        search_term=lei,
                        details={"message": "LEI not found"},
                    )
                resp.raise_for_status()
                data = resp.json()

            record = data.get("data", {})
            return self._parse_record(record, lei)

        except httpx.HTTPStatusError as e:
            raise SourceError("intl.gleif", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("intl.gleif", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.gleif", f"Query failed: {e}") from e

    def _query_by_name(self, name: str) -> IntlGleifResult:
        try:
            logger.info("Querying GLEIF by name: %s", name)
            params = {
                "filter[entity.legalName]": name,
                "page[size]": "5",
            }
            headers = {"Accept": "application/vnd.api+json"}
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(GLEIF_API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            records = data.get("data", [])
            if not records:
                return IntlGleifResult(
                    queried_at=datetime.now(),
                    search_term=name,
                    details={"message": "No LEI records found for this name"},
                )

            return self._parse_record(records[0], name)

        except httpx.HTTPStatusError as e:
            raise SourceError("intl.gleif", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("intl.gleif", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.gleif", f"Query failed: {e}") from e

    def _parse_record(self, record: dict, search_term: str) -> IntlGleifResult:
        lei = record.get("id", "")
        attrs = record.get("attributes", {})
        entity = attrs.get("entity", {})

        legal_name_obj = entity.get("legalName", {})
        legal_name = (
            legal_name_obj.get("name", "")
            if isinstance(legal_name_obj, dict)
            else str(legal_name_obj)
        )

        legal_address = entity.get("legalAddress", {})
        jurisdiction = (
            legal_address.get("country", "")
            if isinstance(legal_address, dict)
            else entity.get("jurisdiction", "")
        )

        entity_status = entity.get("status", "")
        registration = attrs.get("registration", {})

        return IntlGleifResult(
            queried_at=datetime.now(),
            search_term=search_term,
            lei=lei,
            legal_name=legal_name,
            jurisdiction=jurisdiction,
            entity_status=entity_status,
            details={
                "registration_status": registration.get("status", ""),
                "managing_lou": registration.get("managingLou", ""),
                "initial_registration_date": registration.get("initialRegistrationDate", ""),
                "last_update_date": registration.get("lastUpdateDate", ""),
            },
        )
