"""ECLAC/CEPAL statistics source — UN Latin America statistics.

Queries the CEPALSTAT portal for Latin America and Caribbean statistics.
Browser-based source (portal uses JavaScript rendering).

URL: https://statistics.cepal.org/portal/cepalstat/
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.eclac import EclacDataPoint, EclacResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CEPALSTAT_URL = "https://statistics.cepal.org/portal/cepalstat/"
CEPALSTAT_API_URL = "https://api-cepalstat.cepal.org/cepalstat/api/v1/indicator/{indicator}/data"


@register
class EclacSource(BaseSource):
    """Query ECLAC/CEPAL Latin America statistics via the CEPALSTAT portal."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.eclac",
            display_name="ECLAC/CEPAL — Latin America Statistics (CEPALSTAT)",
            description=(
                "UN ECLAC CEPALSTAT portal: social, economic, and environmental "
                "statistics for Latin America and the Caribbean"
            ),
            country="INTL",
            url=CEPALSTAT_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        indicator = input.extra.get("indicator", input.document_number).strip()
        country = input.extra.get("country", "").strip().upper()

        if not indicator:
            raise SourceError(
                "intl.eclac",
                "Provide an indicator code (extra.indicator or document_number)",
            )

        return self._fetch(indicator, country)

    def _fetch(self, indicator: str, country: str) -> EclacResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying CEPALSTAT: indicator=%s country=%s", indicator, country)

            url = CEPALSTAT_API_URL.format(indicator=indicator)
            params = "?members=true&lang=en"
            if country:
                params += f"&country={country}"

            data_points: list[EclacDataPoint] = []
            details = ""

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(url + params, wait_until="networkidle", timeout=self._timeout * 1000)
                content = page.content()

            # Parse JSON from page content
            import json
            import re

            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                body = data.get("body", data)
                indicator_data = body.get("data", []) if isinstance(body, dict) else []
                details = body.get("indicator_name", "") if isinstance(body, dict) else ""

                for record in indicator_data:
                    period = str(record.get("year", record.get("period", "")))
                    raw_val = record.get("value")
                    value_str = str(raw_val) if raw_val is not None else ""
                    if period:
                        data_points.append(EclacDataPoint(period=period, value=value_str))

            return EclacResult(
                queried_at=datetime.now(),
                indicator=indicator,
                country_code=country,
                data_points=data_points,
                details=details,
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.eclac", f"Query failed: {e}") from e
