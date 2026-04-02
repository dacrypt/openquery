"""OFAC SDN List source — US Treasury sanctions screening.

Queries the OFAC Specially Designated Nationals (SDN) list to check
if a person or entity appears on US sanctions lists.

Uses the OFAC sanctions search API for name-based lookups.
No browser or CAPTCHA required — direct HTTP.

API: https://sanctionssearch.ofac.treas.gov/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.ofac import OfacEntry, OfacResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

OFAC_SEARCH_URL = "https://sanctionssearch.ofac.treas.gov/"
OFAC_SDN_XML_URL = "https://www.treasury.gov/ofac/downloads/sdn.xml"
OFAC_API_URL = "https://search.ofac-sdn.treas.gov/search"


@register
class OfacSource(BaseSource):
    """Screen names/entities against the OFAC SDN sanctions list."""

    def __init__(self, timeout: float = 15.0, min_score: float = 80.0) -> None:
        self._timeout = timeout
        self._min_score = min_score

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.ofac",
            display_name="OFAC — US Treasury Sanctions (SDN List)",
            description="US Treasury OFAC Specially Designated Nationals (SDN) sanctions screening",
            country="US",
            url=OFAC_SEARCH_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.NIT, DocumentType.PASSPORT, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        name = input.extra.get("name", "").strip()
        doc_number = input.document_number.strip()

        if not name and not doc_number:
            raise SourceError("us.ofac", "Provide a name (extra.name) or document number to search")

        search_term = name if name else doc_number
        return self._search(search_term)

    def _search(self, query: str) -> OfacResult:
        import xml.etree.ElementTree as ET

        try:
            logger.info("Downloading OFAC SDN XML list...")
            with httpx.Client(timeout=self._timeout, verify=True, follow_redirects=True) as client:
                resp = client.get(OFAC_SDN_XML_URL)
                resp.raise_for_status()
                xml_content = resp.content

            root = ET.fromstring(xml_content)
            ns = {"sdn": "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN_ADVANCED.XML"}

            # Try with and without namespace
            query_lower = query.lower()
            matches = []

            for entry in root.iter():
                if entry.tag.endswith("sdnEntry") or entry.tag == "sdnEntry":
                    uid_elem = entry.find("uid") or entry.find("{*}uid")
                    uid = uid_elem.text if uid_elem is not None and uid_elem.text else ""

                    # Get names
                    name_parts = []
                    for tag in ("firstName", "lastName", "{*}firstName", "{*}lastName"):
                        elem = entry.find(tag)
                        if elem is not None and elem.text:
                            name_parts.append(elem.text.strip())

                    full_name = " ".join(name_parts)
                    if not full_name:
                        continue

                    if query_lower not in full_name.lower():
                        continue

                    sdn_type_elem = entry.find("sdnType") or entry.find("{*}sdnType")
                    sdn_type = sdn_type_elem.text if sdn_type_elem is not None else ""

                    remarks_elem = entry.find("remarks") or entry.find("{*}remarks")
                    remarks = remarks_elem.text[:200] if remarks_elem is not None and remarks_elem.text else ""

                    # Get programs
                    programs = []
                    for prog in entry.iter():
                        if prog.tag.endswith("program") or prog.tag == "program":
                            if prog.text:
                                programs.append(prog.text.strip())

                    matches.append(OfacEntry(
                        uid=uid,
                        name=full_name,
                        type=sdn_type,
                        programs=programs,
                        remarks=remarks,
                        score=100.0,  # Exact XML match
                    ))

            return OfacResult(
                queried_at=datetime.now(),
                query=query,
                match_count=len(matches),
                is_sanctioned=len(matches) > 0,
                matches=matches,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("us.ofac", f"OFAC API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("us.ofac", f"Request failed: {e}") from e
        except ET.ParseError as e:
            raise SourceError("us.ofac", f"Failed to parse OFAC SDN XML: {e}") from e
        except Exception as e:
            raise SourceError("us.ofac", f"OFAC search failed: {e}") from e
