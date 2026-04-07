"""Electricity Maps source — carbon intensity of electricity by zone.

Queries Electricity Maps API for real-time carbon intensity data.
Requires free API key from electricitymaps.com.

API: https://api.electricitymap.org/v3/carbon-intensity/latest
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.electricity_maps import IntlElectricityMapsResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://api.electricitymap.org/v3/carbon-intensity/latest"


@register
class ElectricityMapsSource(BaseSource):
    """Query Electricity Maps for carbon intensity of electricity by zone."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.electricity_maps",
            display_name="Electricity Maps — Carbon Intensity",
            description="Real-time carbon intensity (gCO2eq/kWh) and fossil fuel percentage by electricity zone",  # noqa: E501
            country="INTL",
            url="https://app.electricitymaps.com/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        from openquery.config import get_settings

        settings = get_settings()
        api_key = settings.electricitymaps_api_key
        if not api_key:
            raise SourceError(
                "intl.electricity_maps",
                "OPENQUERY_ELECTRICITYMAPS_API_KEY is not configured",
            )

        zone = (input.extra.get("zone") or input.document_number or "").strip()
        if not zone:
            raise SourceError("intl.electricity_maps", "Provide extra['zone'] (e.g. 'CO', 'BR-S', 'US-CAL-CISO')")  # noqa: E501

        logger.info("Querying Electricity Maps: zone=%s", zone)

        try:
            headers = {
                "auth-token": api_key,
                "Accept": "application/json",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(API_URL, params={"zone": zone})
                resp.raise_for_status()
                data = resp.json()

            carbon_intensity = data.get("carbonIntensity", "")
            fossil_pct = data.get("fossilFuelPercentage", "")
            dt = data.get("datetime", "")

            return IntlElectricityMapsResult(
                zone=zone,
                carbon_intensity=str(carbon_intensity) if carbon_intensity != "" else "",
                fossil_fuel_percentage=str(fossil_pct) if fossil_pct != "" else "",
                measurement_datetime=str(dt),
                details=f"Carbon intensity {carbon_intensity} gCO2eq/kWh for zone {zone}",
            )

        except SourceError:
            raise
        except httpx.HTTPStatusError as e:
            raise SourceError("intl.electricity_maps", f"API returned HTTP {e.response.status_code}") from e  # noqa: E501
        except httpx.RequestError as e:
            raise SourceError("intl.electricity_maps", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("intl.electricity_maps", f"Query failed: {e}") from e
