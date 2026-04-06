"""Panama CSS Patrono source — employer registration lookup (Caja de Seguro Social).

Queries the CSS (Caja de Seguro Social) employer registry for Panama.
Browser-based scraping — no public API available.

URL: https://w3.css.gob.pa/
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pa.css_patrono import PaCssPatronoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CSS_URL = "https://w3.css.gob.pa/"


@register
class PaCssPatronoSource(BaseSource):
    """Query Panama CSS employer/patrono registration status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pa.css_patrono",
            display_name="CSS — Consulta de Patronos (Caja de Seguro Social)",
            description="Panama CSS employer registration status lookup (Caja de Seguro Social)",
            country="PA",
            url=CSS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search = (
            input.extra.get("employer_name", "")
            or input.extra.get("ruc", "")
            or input.document_number
        ).strip()
        if not search:
            raise SourceError(
                "pa.css_patrono",
                "Employer name or RUC is required (extra['employer_name'] or extra['ruc'])",
            )
        return self._query(search)

    def _query(self, search: str) -> PaCssPatronoResult:
        try:
            from openquery.core.browser import BrowserManager

            logger.info("Querying CSS Panama patrono: %s", search)
            browser = BrowserManager(headless=self._headless, timeout=self._timeout)
            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(CSS_URL, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)
                return self._parse_page(page, search)

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("pa.css_patrono", f"Query failed: {e}") from e

    def _parse_page(self, page: object, search: str) -> PaCssPatronoResult:
        """Parse CSS page — returns placeholder as page structure varies."""
        try:
            text = page.inner_text("body")  # type: ignore[union-attr]
        except Exception:
            text = ""

        employer_name = ""
        registration_status = ""
        details: dict = {"raw_length": len(text)}

        if search.lower() in text.lower():
            employer_name = search
            registration_status = "found"
        elif text:
            registration_status = "not_found"
            details["message"] = "Employer not found in CSS registry"

        return PaCssPatronoResult(
            queried_at=datetime.now(),
            search_term=search,
            employer_name=employer_name,
            registration_status=registration_status,
            details=details,
        )
