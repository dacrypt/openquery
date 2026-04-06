"""UN Comtrade source — international trade statistics (public preview API).

Free REST API (public preview tier), no auth required for basic queries.

API: https://comtradeapi.un.org/public/v1/preview/C/A/M/000/TOTAL/{reporter}
Docs: https://comtradeapi.un.org/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.un_comtrade import ComtradePartner, IntlUnComtradeResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

COMTRADE_BASE = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"


@register
class IntlUnComtradeSource(BaseSource):
    """Query UN Comtrade for international trade statistics by reporter country."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.un_comtrade",
            display_name="UN Comtrade — International Trade Statistics",
            description="UN Comtrade public trade statistics: imports/exports by country and commodity",  # noqa: E501
            country="INTL",
            url="https://comtradeapi.un.org/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        reporter = (input.extra.get("reporter", "") or input.document_number).strip()
        commodity_code = input.extra.get("commodity_code", "TOTAL").strip() or "TOTAL"
        if not reporter:
            raise SourceError(
                "intl.un_comtrade",
                "Reporter country code is required (e.g. '484' for Mexico, '76' for Brazil)",
            )
        return self._query(reporter, commodity_code)

    def _query(self, reporter: str, commodity_code: str) -> IntlUnComtradeResult:
        try:
            # Public preview endpoint: /C/A/HS/{cmdCode}/{reporter}
            url = f"{COMTRADE_BASE}/{commodity_code}/{reporter}"
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/1.0)",
                "Accept": "application/json",
            }
            logger.info("Querying UN Comtrade: reporter=%s commodity=%s", reporter, commodity_code)
            with httpx.Client(timeout=self._timeout, headers=headers, follow_redirects=True) as client:  # noqa: E501
                resp = client.get(url)
                if resp.status_code in (404, 400):
                    return IntlUnComtradeResult(
                        queried_at=datetime.now(),
                        reporter=reporter,
                        commodity_code=commodity_code,
                        details={"message": f"No data found (HTTP {resp.status_code})"},
                    )
                resp.raise_for_status()
                data = resp.json()

            return self._parse_response(data, reporter, commodity_code)

        except httpx.HTTPStatusError as e:
            raise SourceError("intl.un_comtrade", f"API returned HTTP {e.response.status_code}") from e  # noqa: E501
        except httpx.RequestError as e:
            raise SourceError("intl.un_comtrade", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.un_comtrade", f"Query failed: {e}") from e

    def _parse_response(self, data: dict, reporter: str, commodity_code: str) -> IntlUnComtradeResult:  # noqa: E501
        records = data.get("data", data.get("Dataset", []))
        if isinstance(records, dict):
            records = [records]

        partners: list[ComtradePartner] = []
        total_value: float = 0.0

        for rec in records[:50]:
            trade_val = rec.get("primaryValue", rec.get("TradeValue"))
            partner_code = str(rec.get("partnerCode", rec.get("ptCode", "")))
            partner_desc = rec.get("partnerDesc", rec.get("ptTitle", ""))
            flow = rec.get("flowDesc", rec.get("rgDesc", ""))

            if trade_val is not None:
                try:
                    tv = float(trade_val)
                    total_value += tv
                    partners.append(ComtradePartner(
                        partner_code=partner_code,
                        partner_desc=str(partner_desc),
                        trade_value=tv,
                        flow=str(flow),
                    ))
                except (ValueError, TypeError):
                    pass

        return IntlUnComtradeResult(
            queried_at=datetime.now(),
            reporter=reporter,
            commodity_code=commodity_code,
            total_trade_value=total_value if total_value else None,
            partners=partners,
            details={"record_count": len(records)},
        )
