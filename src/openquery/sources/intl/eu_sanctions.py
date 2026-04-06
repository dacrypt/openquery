"""EU Consolidated Sanctions List source.

Downloads and searches the EU Financial Sanctions File (FSF) XML list.
No auth required. Rate limit: 5 req/min (large XML download, cache recommended).

XML: https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content?token=dG9rZW4tMjAxNw
Portal: https://webgate.ec.europa.eu/fsd/fsf/
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.eu_sanctions import EuSanctionEntry, EuSanctionsResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

EU_XML_URL = (
    "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content"
    "?token=dG9rZW4tMjAxNw"
)
EU_PORTAL_URL = "https://webgate.ec.europa.eu/fsd/fsf/"


@register
class EuSanctionsSource(BaseSource):
    """Screen names against the EU Consolidated Sanctions List."""

    def __init__(self, timeout: float = 60.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.eu_sanctions",
            display_name="EU — Consolidated Financial Sanctions List",
            description="EU Financial Sanctions File (FSF): persons, groups and entities subject to EU sanctions",
            country="INTL",
            url=EU_PORTAL_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.NIT, DocumentType.PASSPORT, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=5,
        )

    def query(self, input: QueryInput) -> BaseModel:
        name = input.extra.get("name", "").strip()
        doc_number = input.document_number.strip()

        if not name and not doc_number:
            raise SourceError("intl.eu_sanctions", "Provide a name (extra.name) or document number to search")

        search_term = name if name else doc_number
        return self._search(search_term)

    def _search(self, query: str) -> EuSanctionsResult:
        try:
            logger.info("Downloading EU sanctions XML list")
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                resp = client.get(EU_XML_URL)
                resp.raise_for_status()
                xml_content = resp.content

            root = ET.fromstring(xml_content)
            query_lower = query.lower()
            entries: list[EuSanctionEntry] = []

            # The EU FSF XML schema uses <sanctionEntity> elements
            for entity in root.iter("sanctionEntity"):
                # Collect all name aliases
                name_texts: list[str] = []
                for name_alias in entity.iter("nameAlias"):
                    full_name = name_alias.get("wholeName", "").strip()
                    if full_name:
                        name_texts.append(full_name)

                matched_name = next((n for n in name_texts if query_lower in n.lower()), None)
                if matched_name is None:
                    continue

                subject_type = entity.get("subjectType", "")
                regulation = entity.find("regulation")
                program = ""
                listed_date = ""
                if regulation is not None:
                    program = regulation.get("programme", "")
                    listed_date = regulation.get("entryIntoForceDate", "")

                # Build details from remark elements
                remarks: list[str] = []
                for remark in entity.iter("remark"):
                    if remark.text:
                        remarks.append(remark.text.strip())
                details = "; ".join(remarks[:3])

                entries.append(EuSanctionEntry(
                    name=matched_name,
                    entity_type=subject_type,
                    program=program,
                    listed_date=listed_date,
                    details=details[:300],
                ))

            return EuSanctionsResult(
                queried_at=datetime.now(),
                search_term=query,
                total=len(entries),
                entries=entries,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError("intl.eu_sanctions", f"EU API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("intl.eu_sanctions", f"Request failed: {e}") from e
        except ET.ParseError as e:
            raise SourceError("intl.eu_sanctions", f"Failed to parse EU sanctions XML: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.eu_sanctions", f"EU sanctions search failed: {e}") from e
