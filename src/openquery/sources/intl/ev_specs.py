"""EV specs source — Open EV Data battery/range specs.

Queries Open EV Data static JSON dataset for electric vehicle specifications.
Free, no auth required. Cached static file from GitHub.

API: https://raw.githubusercontent.com/open-ev-data/open-ev-data-dataset/main/data/ev-data.json
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.ev_specs import IntlEvSpecsResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DATA_URL = "https://raw.githubusercontent.com/open-ev-data/open-ev-data-dataset/main/data/ev-data.json"


@register
class EvSpecsSource(BaseSource):
    """Query Open EV Data for electric vehicle specifications."""

    def __init__(self, timeout: float = 20.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.ev_specs",
            display_name="Open EV Data — EV Battery & Range Specs",
            description="Electric vehicle specifications (battery, range, charge rates) from Open EV Data dataset",  # noqa: E501
            country="INTL",
            url="https://github.com/open-ev-data/open-ev-data-dataset",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        brand = input.extra.get("brand", "").strip().lower()
        model = input.extra.get("model", "").strip().lower()

        if not brand and not model:
            raise SourceError("intl.ev_specs", "Provide extra['brand'] and/or extra['model']")

        logger.info("Querying Open EV Data: brand=%s model=%s", brand, model)

        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(DATA_URL)
                resp.raise_for_status()
                data = resp.json()

            # Dataset may be a list or dict with 'data' key
            vehicles = data if isinstance(data, list) else data.get("data", [])

            matches = []
            for v in vehicles:
                v_brand = str(v.get("brand", "")).lower()
                v_model = str(v.get("model", "")).lower()
                brand_match = not brand or brand in v_brand
                model_match = not model or model in v_model
                if brand_match and model_match:
                    matches.append(v)

            if not matches:
                return IntlEvSpecsResult(
                    brand=brand,
                    model=model,
                    details=f"No EV found matching brand='{brand}' model='{model}'",
                )

            # Return first match fields + all matches list
            first = matches[0]
            return IntlEvSpecsResult(
                brand=str(first.get("brand", "")),
                model=str(first.get("model", "")),
                battery_capacity_kwh=str(first.get("usable_battery_size", first.get("battery_capacity", ""))),  # noqa: E501
                range_km=str(first.get("range", first.get("range_real", ""))),
                fast_charge_kw=str(first.get("fast_charge_speed", first.get("fastcharge_speed", ""))),  # noqa: E501
                connector_type=str(first.get("connector", first.get("plug_type", ""))),
                details=f"{len(matches)} match(es) found",
                matches=matches[:10],
            )

        except SourceError:
            raise
        except httpx.HTTPStatusError as e:
            raise SourceError("intl.ev_specs", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("intl.ev_specs", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("intl.ev_specs", f"Query failed: {e}") from e
