"""NHTSA VIN Decode source — US vehicle identification number decoder.

Decodes a 17-character VIN via the NHTSA vPIC (Vehicle Product Information
Catalog) API.  Returns make, model, year, body class, fuel type, and every
other non-empty field the API provides.

No browser or CAPTCHA required — direct HTTP API.

API: https://vpic.nhtsa.dot.gov/api/
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.nhtsa_vin import NhtsaVinResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/decodevin"

# Fields we promote to top-level model attributes.
_KEY_FIELDS: dict[str, str] = {
    "Make": "make",
    "Model": "model",
    "Model Year": "model_year",
    "Body Class": "body_class",
    "Vehicle Type": "vehicle_type",
    "Plant City": "plant_city",
    "Plant Country": "plant_country",
    "Manufacturer Name": "manufacturer",
    "Fuel Type - Primary": "fuel_type",
    "Engine Number of Cylinders": "engine_cylinders",
    "Displacement (L)": "displacement_l",
    "Drive Type": "drive_type",
    "GVWR": "gvwr",
    "Electrification Level": "electrification",
    "Battery kWh": "battery_kwh",
}


@register
class NhtsaVinSource(BaseSource):
    """Decode a VIN using the NHTSA vPIC API."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.nhtsa_vin",
            display_name="NHTSA — VIN Decode",
            description="US NHTSA vPIC VIN decoder (vehicle identification number)",
            country="US",
            url="https://vpic.nhtsa.dot.gov/api/",
            supported_inputs=[DocumentType.VIN],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Decode a VIN and return structured vehicle data."""
        if input.document_type != DocumentType.VIN:
            raise SourceError("us.nhtsa_vin", f"Unsupported input type: {input.document_type}")

        vin = input.document_number.strip().upper()
        if not vin:
            raise SourceError("us.nhtsa_vin", "VIN is required")

        try:
            url = f"{API_URL}/{vin}"
            logger.info("Decoding VIN %s via NHTSA vPIC", vin)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(url, params={"format": "json"})
                resp.raise_for_status()
                data = resp.json()

            results = data.get("Results", [])

            # Build all_fields dict (skip empty values)
            all_fields: dict[str, str] = {}
            for item in results:
                variable = item.get("Variable", "")
                value = (item.get("Value") or "").strip()
                if value and variable:
                    all_fields[variable] = value

            # Populate the result model
            result = NhtsaVinResult(
                queried_at=datetime.now(),
                vin=vin,
                all_fields=all_fields,
            )

            # Map key fields to top-level attributes
            for api_key, attr in _KEY_FIELDS.items():
                val = all_fields.get(api_key, "")
                setattr(result, attr, val)

            logger.info("Decoded VIN %s: %s %s %s", vin, result.make, result.model, result.model_year)
            return result

        except httpx.HTTPStatusError as e:
            raise SourceError("us.nhtsa_vin", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("us.nhtsa_vin", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("us.nhtsa_vin", f"VIN decode failed: {e}") from e
