"""ONU Sanctions source — UN Security Council Consolidated Sanctions List.

Queries the UN Security Council consolidated sanctions list to check
if a person or entity is subject to UN sanctions.

Downloads and searches the XML sanctions list.
No browser or CAPTCHA required — direct HTTP.

Source: https://www.un.org/securitycouncil/sanctions/un-sc-consolidated-list
XML: https://scsanctions.un.org/resources/xml/en/consolidated.xml
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.onu import OnuEntry, OnuResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ONU_XML_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
ONU_PAGE_URL = "https://www.un.org/securitycouncil/sanctions/un-sc-consolidated-list"


@register
class OnuSource(BaseSource):
    """Screen names against the UN Security Council sanctions list."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.onu",
            display_name="ONU — UN Security Council Sanctions",
            description="UN Security Council Consolidated Sanctions List screening",
            country="INTL",
            url=ONU_PAGE_URL,
            supported_inputs=[
                DocumentType.CEDULA,
                DocumentType.NIT,
                DocumentType.PASSPORT,
                DocumentType.CUSTOM,
            ],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        name = input.extra.get("name", "").strip()
        doc_number = input.document_number.strip()

        if not name and not doc_number:
            raise SourceError(
                "intl.onu", "Provide a name (extra.name) or document number to search"
            )

        search_term = name if name else doc_number
        return self._search(search_term)

    def _search(self, query: str) -> OnuResult:
        try:
            with httpx.Client(timeout=self._timeout, verify=True, follow_redirects=True) as client:
                resp = client.get(ONU_XML_URL)
                resp.raise_for_status()
                xml_content = resp.content

            root = ET.fromstring(xml_content)
            query_lower = query.lower()
            matches = []

            # Search individuals
            for individual in root.iter("INDIVIDUAL"):
                name_parts = []
                for tag in ("FIRST_NAME", "SECOND_NAME", "THIRD_NAME"):
                    elem = individual.find(tag)
                    if elem is not None and elem.text:
                        name_parts.append(elem.text.strip())

                full_name = " ".join(name_parts)

                if query_lower in full_name.lower():
                    ref = individual.find("REFERENCE_NUMBER")
                    listed = individual.find("LISTED_ON")
                    comments = individual.find("COMMENTS1")
                    nationality_elem = individual.find(".//NATIONALITY/VALUE")
                    designation = individual.find(".//DESIGNATION/VALUE")
                    list_type = individual.find("UN_LIST_TYPE")

                    matches.append(
                        OnuEntry(
                            reference_number=ref.text if ref is not None and ref.text else "",
                            name=full_name,
                            un_list_type=list_type.text
                            if list_type is not None and list_type.text
                            else "",
                            listed_on=listed.text if listed is not None and listed.text else "",
                            comments=comments.text[:200]
                            if comments is not None and comments.text
                            else "",
                            nationality=nationality_elem.text
                            if nationality_elem is not None and nationality_elem.text
                            else "",
                            designation=designation.text
                            if designation is not None and designation.text
                            else "",
                        )
                    )

            # Search entities
            for entity in root.iter("ENTITY"):
                name_elem = entity.find("FIRST_NAME")
                if name_elem is None or not name_elem.text:
                    continue

                entity_name = name_elem.text.strip()
                if query_lower in entity_name.lower():
                    ref = entity.find("REFERENCE_NUMBER")
                    listed = entity.find("LISTED_ON")
                    comments = entity.find("COMMENTS1")
                    list_type = entity.find("UN_LIST_TYPE")

                    matches.append(
                        OnuEntry(
                            reference_number=ref.text if ref is not None and ref.text else "",
                            name=entity_name,
                            un_list_type=list_type.text
                            if list_type is not None and list_type.text
                            else "",
                            listed_on=listed.text if listed is not None and listed.text else "",
                            comments=comments.text[:200]
                            if comments is not None and comments.text
                            else "",
                        )
                    )

            return OnuResult(
                queried_at=datetime.now(),
                query=query,
                match_count=len(matches),
                is_sanctioned=len(matches) > 0,
                matches=matches,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("intl.onu", f"UN API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("intl.onu", f"Request failed: {e}") from e
        except ET.ParseError as e:
            raise SourceError("intl.onu", f"Failed to parse UN sanctions XML: {e}") from e
        except Exception as e:
            raise SourceError("intl.onu", f"UN sanctions search failed: {e}") from e
