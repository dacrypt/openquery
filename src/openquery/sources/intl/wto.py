"""WTO timeseries trade profiles / tariff data source.

Queries the WTO Timeseries REST API for trade data, tariff profiles, and
merchandise statistics by reporter country and indicator code.

API: https://api.wto.org/timeseries/v1/data
Docs: https://apiportal.wto.org/
Auth: Ocp-Apim-Subscription-Key header (free registration at apiportal.wto.org)
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.config import get_settings
from openquery.exceptions import SourceError
from openquery.models.intl.wto import WtoDataPoint, WtoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

WTO_API_URL = "https://api.wto.org/timeseries/v1/data"


@register
class WtoSource(BaseSource):
    """Query WTO timeseries API for trade profiles and tariff data."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.wto",
            display_name="WTO — Trade Profiles & Tariff Data",
            description=(
                "WTO Timeseries API for trade data, tariff profiles, and merchandise statistics "
                "by reporter country and indicator code"
            ),
            country="INTL",
            url="https://api.wto.org/timeseries/v1/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        reporter = (input.extra.get("reporter", "") or input.document_number).strip()
        indicator = input.extra.get("indicator", "HS_M_0010").strip() or "HS_M_0010"

        if not reporter:
            raise SourceError(
                "intl.wto",
                "Reporter country code is required (e.g. '840' for USA, '76' for Brazil)",
            )

        return self._fetch(reporter, indicator)

    def _fetch(self, reporter: str, indicator: str) -> WtoResult:
        settings = get_settings()
        api_key: str = getattr(settings, "wto_api_key", "")

        params: dict[str, str] = {
            "i": indicator,
            "r": reporter,
            "p": "000",
            "ps": "2023",
            "fmt": "json",
            "max": "100",
            "offset": "0",
        }
        headers: dict[str, str] = {
            "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/1.0)",
            "Accept": "application/json",
        }
        if api_key:
            headers["Ocp-Apim-Subscription-Key"] = api_key

        try:
            logger.info("Querying WTO timeseries: reporter=%s indicator=%s", reporter, indicator)
            with httpx.Client(timeout=self._timeout, headers=headers, follow_redirects=True) as client:
                resp = client.get(WTO_API_URL, params=params)
                if resp.status_code in (400, 404):
                    return WtoResult(
                        queried_at=datetime.now(),
                        reporter=reporter,
                        indicator_code=indicator,
                        total=0,
                        data_points=[],
                    )
                resp.raise_for_status()
                data = resp.json()

            return self._parse_response(data, reporter, indicator)

        except httpx.HTTPStatusError as e:
            raise SourceError("intl.wto", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("intl.wto", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.wto", f"Query failed: {e}") from e

    def _parse_response(self, data: dict, reporter: str, indicator: str) -> WtoResult:
        """Parse WTO timeseries API response into WtoResult."""
        # Response structure: {"Dataset": [...], "requestInfo": {...}}
        # or {"data": [...], "total": N}
        records = data.get("Dataset", data.get("data", []))
        if isinstance(records, dict):
            records = [records]

        total = data.get("total", len(records))
        data_points: list[WtoDataPoint] = []

        for rec in records:
            year = str(rec.get("Year", rec.get("period", "")))
            value = str(rec.get("Value", rec.get("value", "")))
            ind_code = rec.get("indicatorCode", rec.get("IndicatorCode", indicator))
            partner = str(rec.get("PartnerEconomy", rec.get("partnerEconomy", "")))
            data_points.append(WtoDataPoint(
                year=year,
                value=value,
                indicator=str(ind_code),
                partner=partner,
            ))

        return WtoResult(
            queried_at=datetime.now(),
            reporter=reporter,
            indicator_code=indicator,
            total=int(total) if total is not None else len(data_points),
            data_points=data_points,
        )
