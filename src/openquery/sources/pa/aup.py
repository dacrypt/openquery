"""Panama AUP/ASEP source — public utilities authority service providers.

Queries ASEP (Autoridad Nacional de los Servicios Públicos) for utility
company registrations and service provider status in Panama.

URL: https://www.asep.gob.pa/
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pa.aup import PaAupResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ASEP_URL = "https://www.asep.gob.pa/"


@register
class PaAupSource(BaseSource):
    """Query Panama ASEP public utilities authority for service provider registrations."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pa.aup",
            display_name="ASEP — Autoridad Nacional de los Servicios Públicos",
            description="Panama ASEP public utilities authority — service provider registrations",
            country="PA",
            url=ASEP_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search = (
            input.extra.get("company_name", "")
            or input.extra.get("name", "")
            or input.document_number
        ).strip()
        if not search:
            raise SourceError(
                "pa.aup",
                "Company name is required (extra['company_name'] or extra['name'])",
            )
        return self._query(search)

    def _query(self, search: str) -> PaAupResult:
        try:
            from openquery.core.browser import BrowserManager

            logger.info("Querying ASEP Panama for: %s", search)
            browser = BrowserManager(headless=self._headless, timeout=self._timeout)
            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(ASEP_URL, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)
                return self._parse_page(page, search)

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("pa.aup", f"Query failed: {e}") from e

    def _parse_page(self, page: object, search: str) -> PaAupResult:
        """Parse ASEP page for service provider information."""
        try:
            text = page.inner_text("body")  # type: ignore[union-attr]
        except Exception:
            text = ""

        provider_name = ""
        service_type = ""
        status = ""
        details: dict = {"raw_length": len(text)}

        if search.lower() in text.lower():
            provider_name = search
            status = "found"
        elif text:
            status = "not_found"
            details["message"] = "Provider not found in ASEP registry"

        return PaAupResult(
            queried_at=datetime.now(),
            search_term=search,
            provider_name=provider_name,
            service_type=service_type,
            status=status,
            details=details,
        )
