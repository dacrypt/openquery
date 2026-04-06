"""FATF high-risk jurisdictions source.

Scrapes the FATF website for countries on the black list (call for action)
and grey list (increased monitoring). Updated approximately 3 times per year.

URL: https://www.fatf-gafi.org/en/countries/black-and-grey-lists.html
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.fatf import IntlFatfResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

FATF_URL = "https://www.fatf-gafi.org/en/countries/black-and-grey-lists.html"


@register
class IntlFatfSource(BaseSource):
    """Check FATF black/grey list status for countries."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.fatf",
            display_name="FATF — High-Risk Jurisdictions (Black & Grey Lists)",
            description="FATF: countries under increased monitoring (grey) or subject to call for action (black)",  # noqa: E501
            country="INTL",
            url=FATF_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=5,
        )

    def query(self, input: QueryInput) -> BaseModel:
        country = (input.extra.get("country", "") or input.document_number).strip()
        return self._fetch(country)

    def _fetch(self, country: str = "") -> IntlFatfResult:
        try:
            logger.info("Fetching FATF lists%s", f" for: {country}" if country else "")

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "text/html,application/xhtml+xml",
            }

            with httpx.Client(
                timeout=self._timeout, headers=headers, follow_redirects=True
            ) as client:
                resp = client.get(FATF_URL)
                resp.raise_for_status()
                html = resp.text

            black_list, grey_list, last_updated = self._parse_lists(html)

            list_type = "none"
            if country:
                country_lower = country.lower()
                if any(country_lower in c.lower() for c in black_list):
                    list_type = "black"
                elif any(country_lower in c.lower() for c in grey_list):
                    list_type = "grey"
                else:
                    list_type = "none"

                details = (
                    f"Country '{country}' is on the FATF {list_type} list"
                    if list_type != "none"
                    else f"Country '{country}' is not on any FATF list"
                )
            else:
                list_type = "all"
                details = f"Black list: {len(black_list)} countries; Grey list: {len(grey_list)} countries"  # noqa: E501

            return IntlFatfResult(
                country=country,
                list_type=list_type,
                last_updated=last_updated,
                black_list=black_list,
                grey_list=grey_list,
                details=details,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "intl.fatf", f"FATF website returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("intl.fatf", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.fatf", f"Query failed: {e}") from e

    def _parse_lists(self, html: str) -> tuple[list[str], list[str], str]:
        """Parse FATF lists from HTML content."""
        black_list: list[str] = []
        grey_list: list[str] = []
        last_updated = ""

        # Extract last updated date
        date_match = re.search(
            r"(?:updated|published)[:\s]+([A-Z][a-z]+ \d{4})", html, re.IGNORECASE
        )
        if date_match:
            last_updated = date_match.group(1)
        else:
            last_updated = datetime.now().strftime("%B %Y")

        # Look for black list section (Call for Action / High-Risk)
        black_pattern = re.compile(
            r"(?:call for action|high.risk jurisdictions)"
            r"[^<]*</[^>]+>(.*?)(?:grey list|increased monitoring|<section)",
            re.IGNORECASE | re.DOTALL,
        )
        black_match = black_pattern.search(html)
        if black_match:
            section = black_match.group(1)
            black_list = self._extract_countries(section)

        # Look for grey list section (Increased Monitoring)
        grey_pattern = re.compile(
            r"(?:grey list|increased monitoring|jurisdictions under increased)"
            r"[^<]*</[^>]+>(.*?)(?:<section|$)",
            re.IGNORECASE | re.DOTALL,
        )
        grey_match = grey_pattern.search(html)
        if grey_match:
            section = grey_match.group(1)
            grey_list = self._extract_countries(section)

        # Fallback: look for <li> elements in country lists
        if not black_list and not grey_list:
            li_pattern = re.compile(r"<li[^>]*>([A-Z][a-zA-Z\s\-'()]+)</li>")
            all_countries = li_pattern.findall(html)
            # Heuristically assign to grey (most common list)
            grey_list = [c.strip() for c in all_countries if 2 < len(c.strip()) < 60][:50]

        return black_list, grey_list, last_updated

    def _extract_countries(self, html_section: str) -> list[str]:
        """Extract country names from an HTML section."""
        # Remove HTML tags
        clean = re.sub(r"<[^>]+>", " ", html_section)
        # Extract <li> country names or lines that look like country names
        countries = re.findall(r"\b([A-Z][a-zA-Z\s\-'().]+?)(?:\n|<|,|;|$)", clean)
        result = []
        for c in countries:
            c = c.strip()
            if 2 < len(c) < 60 and not re.search(r"\d{4}", c):
                result.append(c)
        return result[:30]
