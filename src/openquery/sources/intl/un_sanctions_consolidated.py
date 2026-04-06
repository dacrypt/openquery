"""UN Consolidated Sanctions List source.

Queries the UN Security Council consolidated sanctions list (XML feed).

URL: https://scsanctions.un.org/resources/xml/en/consolidated.xml
Input: name (custom)
Returns: matching sanctioned individuals/entities
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.un_sanctions_consolidated import (
    UnSanctionEntry,
    UnSanctionsConsolidatedResult,
)
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

UN_SANCTIONS_XML_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"


@register
class UnSanctionsConsolidatedSource(BaseSource):
    """Search UN consolidated sanctions list by name."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.un_sanctions_consolidated",
            display_name="UN Consolidated Sanctions List",
            description="UN Security Council consolidated sanctions list: person/entity name search (free XML feed)",  # noqa: E501
            country="INTL",
            url=UN_SANCTIONS_XML_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (input.extra.get("name", "") or input.document_number).strip()
        if not search_term:
            raise SourceError(
                "intl.un_sanctions_consolidated",
                "Name required (extra.name or document_number)",
            )
        return self._search(search_term)

    def _search(self, search_term: str) -> UnSanctionsConsolidatedResult:
        try:
            logger.info("Querying UN Consolidated Sanctions: name=%s", search_term)
            headers = {"User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)"}
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(UN_SANCTIONS_XML_URL)
                resp.raise_for_status()

            root = ET.fromstring(resp.content)
            {"": root.tag.split("}")[0].lstrip("{") if "}" in root.tag else ""}
            entries = []
            search_lower = search_term.lower()

            for individual in root.iter():
                tag = individual.tag.split("}")[-1] if "}" in individual.tag else individual.tag
                if tag not in ("INDIVIDUAL", "ENTITY"):
                    continue

                first = ""
                second = ""
                third = ""
                entity_type = tag.lower()
                reference = ""
                nationality = ""
                designation = ""

                for child in individual:
                    child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    text = (child.text or "").strip()
                    if child_tag == "FIRST_NAME":
                        first = text
                    elif child_tag == "SECOND_NAME":
                        second = text
                    elif child_tag == "THIRD_NAME":
                        third = text
                    elif child_tag == "DATAID":
                        reference = text
                    elif child_tag == "NATIONALITY":
                        for sub in child:
                            sub_tag = sub.tag.split("}")[-1] if "}" in sub.tag else sub.tag
                            if sub_tag == "VALUE":
                                nationality = (sub.text or "").strip()
                    elif child_tag == "DESIGNATION":
                        for sub in child:
                            sub_tag = sub.tag.split("}")[-1] if "}" in sub.tag else sub.tag
                            if sub_tag == "VALUE":
                                designation = (sub.text or "").strip()

                full_name = " ".join(filter(None, [first, second, third]))
                if search_lower in full_name.lower():
                    entries.append(
                        UnSanctionEntry(
                            name=full_name,
                            entity_type=entity_type,
                            list_type="UN",
                            reference_number=reference,
                            nationality=nationality,
                            designation=designation,
                        )
                    )
                    if len(entries) >= 20:
                        break

            return UnSanctionsConsolidatedResult(
                queried_at=datetime.now(),
                search_term=search_term,
                total=len(entries),
                entries=entries,
                details=f"UN Consolidated Sanctions query for: {search_term}",
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "intl.un_sanctions_consolidated", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("intl.un_sanctions_consolidated", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("intl.un_sanctions_consolidated", f"Query failed: {e}") from e
