"""Treasury OFAC SDN source — US sanctions detailed list.

Queries the OFAC (Office of Foreign Assets Control) SDN XML list
for detailed sanctions information. Extends us.ofac with richer fields.

Source: https://www.treasury.gov/ofac/downloads/sdn.xml
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.treasury_ofac_sdn import SdnEntry, TreasuryOfacSdnResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

OFAC_SDN_XML_URL = "https://www.treasury.gov/ofac/downloads/sdn.xml"
OFAC_URL = "https://sanctionssearch.ofac.treas.gov/"


@register
class TreasuryOfacSdnSource(BaseSource):
    """Query OFAC SDN list with full entry details (programs, type, remarks)."""

    def __init__(self, timeout: float = 60.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.treasury_ofac_sdn",
            display_name="Treasury OFAC — SDN List (Detailed)",
            description="US Treasury OFAC SDN list with full entry details: programs, entity type, and remarks",  # noqa: E501
            country="US",
            url=OFAC_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("name", "")
            or input.document_number
        ).strip()
        if not search_term:
            raise SourceError(
                "us.treasury_ofac_sdn",
                "Name required (pass via extra.name or document_number)",
            )
        return self._search(search_term)

    def _search(self, query: str) -> TreasuryOfacSdnResult:
        import xml.etree.ElementTree as ET

        try:
            logger.info("Downloading OFAC SDN XML list...")
            with httpx.Client(timeout=self._timeout, verify=True, follow_redirects=True) as client:
                resp = client.get(OFAC_SDN_XML_URL)
                resp.raise_for_status()
                xml_content = resp.content

            root = ET.fromstring(xml_content)
            query_lower = query.lower()
            matches: list[SdnEntry] = []

            for entry in root.iter():
                if entry.tag.endswith("sdnEntry") or entry.tag == "sdnEntry":
                    uid_elem = entry.find("uid") or entry.find("{*}uid")
                    uid = uid_elem.text if uid_elem is not None and uid_elem.text else ""

                    name_parts = []
                    for tag in ("firstName", "lastName", "{*}firstName", "{*}lastName"):
                        elem = entry.find(tag)
                        if elem is not None and elem.text:
                            name_parts.append(elem.text.strip())
                    full_name = " ".join(name_parts)
                    if not full_name or query_lower not in full_name.lower():
                        continue

                    sdn_type_elem = entry.find("sdnType") or entry.find("{*}sdnType")
                    sdn_type = sdn_type_elem.text if sdn_type_elem is not None else ""

                    remarks_elem = entry.find("remarks") or entry.find("{*}remarks")
                    remarks = (
                        remarks_elem.text[:300]
                        if remarks_elem is not None and remarks_elem.text
                        else ""
                    )

                    programs = []
                    for prog in entry.iter():
                        if prog.tag.endswith("program") or prog.tag == "program":
                            if prog.text:
                                programs.append(prog.text.strip())

                    matches.append(
                        SdnEntry(
                            uid=uid,
                            name=full_name,
                            sdn_type=sdn_type,
                            programs=programs,
                            remarks=remarks,
                        )
                    )

            return TreasuryOfacSdnResult(
                queried_at=datetime.now(),
                search_term=query,
                total=len(matches),
                sdn_entries=matches,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "us.treasury_ofac_sdn", f"OFAC API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("us.treasury_ofac_sdn", f"Request failed: {e}") from e
        except ET.ParseError as e:
            raise SourceError("us.treasury_ofac_sdn", f"Failed to parse OFAC SDN XML: {e}") from e
        except Exception as e:
            raise SourceError("us.treasury_ofac_sdn", f"OFAC SDN search failed: {e}") from e
