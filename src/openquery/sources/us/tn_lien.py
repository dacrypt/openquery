"""Tennessee motor vehicle temporary lien search source.

Queries the Tennessee Secretary of State MVTL portal for active motor vehicle
temporary liens (180-day window).

Flow:
1. Navigate to https://tncab.tnsos.gov/portal/mvtl-search
2. Select search type (VIN, debtor name, or document number)
3. Fill the search field
4. Submit the form
5. Parse the results table
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.tn_lien import TnLienRecord, TnLienResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

TN_LIEN_URL = "https://tncab.tnsos.gov/portal/mvtl-search"


@register
class TnLienSource(BaseSource):
    """Query Tennessee SOS MVTL portal for active motor vehicle temporary liens."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.tn_lien",
            display_name="Tennessee MVTL — Motor Vehicle Temporary Lien Search",
            description=(
                "Tennessee Secretary of State motor vehicle temporary lien search — "
                "active liens within the 180-day filing window"
            ),
            country="US",
            url=TN_LIEN_URL,
            supported_inputs=[DocumentType.VIN, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query Tennessee MVTL portal for lien records."""
        if input.document_type == DocumentType.VIN:
            search_type = "vin"
            search_value = input.document_number.strip().upper()
        elif input.document_type == DocumentType.CUSTOM:
            search_type = input.extra.get("search_type", "vin")
            if search_type not in ("vin", "debtor", "document"):
                raise SourceError(
                    "us.tn_lien",
                    f"Invalid search_type '{search_type}'. Must be 'vin', 'debtor', or 'document'.",
                )
            search_value = input.document_number.strip()
            if search_type == "vin":
                search_value = search_value.upper()
        else:
            raise SourceError("us.tn_lien", f"Unsupported input type: {input.document_type}")

        if not search_value:
            raise SourceError("us.tn_lien", "Search value is required")

        return self._query(search_value, search_type, audit=input.audit)

    def _query(self, search_value: str, search_type: str, audit: bool = False) -> TnLienResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("us.tn_lien", search_type, search_value)

        with browser.page(TN_LIEN_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                logger.info("Waiting for TN MVTL search form...")

                # The form uses radio buttons for search type:
                # "Individual's Name" (default), "Organization Name",
                # "Document Number", "VIN Number"
                # Map our search_type values to the radio button labels.
                radio_label_map = {
                    "vin": "VIN Number",
                    "debtor": "Individual's Name",
                    "document": "Document Number",
                }
                radio_label = radio_label_map.get(search_type, "VIN Number")
                search_radio = page.get_by_role("radio", name=radio_label)
                search_radio.wait_for(state="visible", timeout=15000)
                search_radio.click()
                logger.info("Selected search type radio: %s", radio_label)

                # After selecting VIN, the VIN input appears with placeholder
                # "Enter VIN Number". For other types, appropriate fields appear.
                placeholder_map = {
                    "vin": "Enter VIN Number",
                    "debtor": "Enter Last Name",
                    "document": "Enter an MVTL Document Number",
                }
                placeholder = placeholder_map.get(search_type, "Enter VIN Number")
                search_input = page.get_by_placeholder(placeholder)
                search_input.wait_for(state="visible", timeout=10000)
                search_input.fill(search_value)
                logger.info("Filled search field: %s (%s)", search_value, search_type)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit — the Search button has Kendo UI styling but is a standard button
                submit_btn = page.get_by_role("button", name="Search")
                submit_btn.click()
                logger.info("Clicked Search button")

                # Wait for results — Kendo UI grid or no-results message
                page.wait_for_selector(
                    ".k-grid, .k-grid-content, table, [class*='result'], [class*='no-result'], p",
                    timeout=20000,
                )
                page.wait_for_timeout(1500)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_results(page, search_value, search_type)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("us.tn_lien", f"Query failed: {e}") from e

    def _parse_results(self, page, search_value: str, search_type: str) -> TnLienResult:
        """Parse the MVTL results page."""
        result = TnLienResult(
            queried_at=datetime.now(),
            search_value=search_value,
            search_type=search_type,
        )

        liens: list[TnLienRecord] = []

        # Try to parse a results table
        try:
            rows = page.query_selector_all("table tbody tr")
            if rows:
                for row in rows:
                    cells = row.query_selector_all("td")
                    texts = [c.inner_text().strip() for c in cells]
                    if not any(texts):
                        continue
                    # Map columns heuristically — portals vary; capture what we can
                    record = TnLienRecord(
                        document_number=texts[0] if len(texts) > 0 else "",
                        debtor_name=texts[1] if len(texts) > 1 else "",
                        lienholder=texts[2] if len(texts) > 2 else "",
                        filing_date=texts[3] if len(texts) > 3 else "",
                        status=texts[4] if len(texts) > 4 else "",
                    )
                    liens.append(record)
        except Exception as exc:
            logger.debug("Table parse failed: %s", exc)

        result.liens = liens
        result.total_liens = len(liens)

        logger.info(
            "TN MVTL results — search_type=%s, value=%s, liens=%d",
            search_type,
            search_value,
            result.total_liens,
        )
        return result
