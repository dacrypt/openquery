"""UNDP Human Development Index source.

Queries the UNDP HDR API for Human Development Index data.
Free REST API, no auth, no CAPTCHA.

API: https://hdrapi.undp.org/v3/foobar/databyindicator/137506
Docs: https://hdr.undp.org/data-center/human-development-index
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.undp_hdi import UndpHdiResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

HDI_URL = "https://hdr.undp.org/data-center/human-development-index"
HDI_API_URL = "https://hdrapi.undp.org/v3/foobar/databyindicator/137506"


@register
class UndpHdiSource(BaseSource):
    """Query UNDP Human Development Index by country."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.undp_hdi",
            display_name="UNDP — Human Development Index",
            description="UNDP Human Development Index (HDI) score and rank by country",
            country="INTL",
            url=HDI_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        country = input.extra.get("country", input.document_number).strip()
        if not country:
            raise SourceError(
                "intl.undp_hdi",
                "Provide a country name or ISO code (extra.country or document_number)",
            )
        return self._fetch(country)

    def _fetch(self, country: str) -> UndpHdiResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying UNDP HDI: country=%s", country)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(HDI_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[type='search'], input[type='text'], input[placeholder*='country' i]"
                )
                if search_input:
                    search_input.fill(country)
                    page.keyboard.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                country_lower = country.lower()

                hdi_score = ""
                hdi_rank = ""

                for line in body_text.split("\n"):
                    line_stripped = line.strip()
                    line_lower = line_stripped.lower()
                    if country_lower in line_lower:
                        # Try to extract HDI score (typically 0.xxx format)
                        import re

                        score_match = re.search(r"\b0\.\d{3}\b", line_stripped)
                        if score_match and not hdi_score:
                            hdi_score = score_match.group()
                        rank_match = re.search(r"\b(\d{1,3})\b", line_stripped)
                        if rank_match and not hdi_rank:
                            hdi_rank = rank_match.group()

            return UndpHdiResult(
                queried_at=datetime.now(),
                country=country,
                hdi_score=hdi_score,
                hdi_rank=hdi_rank,
                details=f"UNDP HDI query for: {country}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.undp_hdi", f"Query failed: {e}") from e
