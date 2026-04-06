"""OSHA workplace inspections source.

Queries the OSHA Enforcement Data portal for workplace inspections
and violations by company name. Browser-based source.

URL: https://enforcedata.dol.gov/views/oshaFilter.php
Docs: https://enforcedata.dol.gov/
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.osha import OshaResult, OshaViolation
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

OSHA_URL = "https://enforcedata.dol.gov/views/oshaFilter.php"
OSHA_API_URL = "https://data.dol.gov/get/osha_inspection/rows/100/filter/estab_name"


@register
class OshaSource(BaseSource):
    """Query OSHA enforcement data for workplace inspections by company name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.osha",
            display_name="OSHA — Workplace Inspections and Violations",
            description=(
                "OSHA enforcement data: workplace inspections, violations, "
                "and penalties by company name"
            ),
            country="US",
            url=OSHA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("company_name", input.document_number).strip()

        if not search_term:
            raise SourceError(
                "us.osha",
                "Provide a company name (extra.company_name or document_number)",
            )

        return self._fetch(search_term)

    def _fetch(self, search_term: str) -> OshaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying OSHA enforcement data: company=%s", search_term)

            violations: list[OshaViolation] = []
            total_inspections = 0

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(OSHA_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)

                # Fill the establishment name field
                name_input = page.query_selector(
                    "input[name='estab_name'], input[id*='estab'], input[placeholder*='name' i]"
                )
                if name_input:
                    name_input.fill(search_term)

                    # Submit the form
                    submit_btn = page.query_selector(
                        "input[type='submit'], button[type='submit']"
                    )
                    if submit_btn:
                        submit_btn.click()
                    else:
                        page.keyboard.press("Enter")

                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                # Parse results table
                rows = page.query_selector_all("table tbody tr, .result-row")
                total_inspections = len(rows)

                for row in rows[:20]:
                    cells = row.query_selector_all("td")
                    if len(cells) >= 3:
                        citation = cells[0].inner_text().strip() if cells else ""
                        description = cells[1].inner_text().strip() if len(cells) > 1 else ""
                        penalty = cells[2].inner_text().strip() if len(cells) > 2 else ""
                        severity = cells[3].inner_text().strip() if len(cells) > 3 else ""
                        violations.append(
                            OshaViolation(
                                citation_id=citation,
                                description=description[:200],
                                penalty=penalty,
                                severity=severity,
                            )
                        )

            return OshaResult(
                queried_at=datetime.now(),
                search_term=search_term,
                total_inspections=total_inspections,
                violations=violations,
                details=f"OSHA inspections for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("us.osha", f"Query failed: {e}") from e
