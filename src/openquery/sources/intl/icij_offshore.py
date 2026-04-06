"""ICIJ Offshore Leaks database source.

Queries the ICIJ Offshore Leaks public API for offshore entity data.

URL: https://offshoreleaks.icij.org/
API: https://offshoreleaks.icij.org/search?q=<name>&format=json
Input: name (custom)
Returns: matching offshore entities
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.icij_offshore import IcijOffshoreEntity, IcijOffshoreResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ICIJ_SEARCH_URL = "https://offshoreleaks.icij.org/search"


@register
class IcijOffshoreSource(BaseSource):
    """Search ICIJ Offshore Leaks database by name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.icij_offshore",
            display_name="ICIJ Offshore Leaks Database",
            description="ICIJ Offshore Leaks: search Panama Papers, Pandora Papers, and other leak data by name",  # noqa: E501
            country="INTL",
            url=ICIJ_SEARCH_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (input.extra.get("name", "") or input.document_number).strip()
        if not search_term:
            raise SourceError(
                "intl.icij_offshore",
                "Name required (extra.name or document_number)",
            )
        return self._search(search_term, audit=input.audit)

    def _search(self, search_term: str, audit: bool = False) -> IcijOffshoreResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying ICIJ Offshore Leaks: name=%s", search_term)
            url = f"{ICIJ_SEARCH_URL}?q={search_term}"

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                body_lower = body_text.lower()

                entities = []
                total = 0

                rows = page.query_selector_all("table tr, .search-result, .result-item")
                for row in rows[:20]:
                    row_text = row.inner_text().strip()
                    if row_text and search_term.lower() in row_text.lower():
                        entities.append(
                            IcijOffshoreEntity(
                                name=row_text[:200],
                                entity_type="unknown",
                                dataset="ICIJ Offshore Leaks",
                            )
                        )

                if not entities and search_term.lower() in body_lower:
                    for line in body_text.split("\n"):
                        if search_term.lower() in line.lower() and line.strip():
                            entities.append(
                                IcijOffshoreEntity(
                                    name=line.strip()[:200],
                                    entity_type="unknown",
                                    dataset="ICIJ Offshore Leaks",
                                )
                            )
                            if len(entities) >= 10:
                                break

                total = len(entities)

            return IcijOffshoreResult(
                queried_at=datetime.now(),
                search_term=search_term,
                total=total,
                entities=entities,
                details=f"ICIJ Offshore Leaks query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.icij_offshore", f"Query failed: {e}") from e
