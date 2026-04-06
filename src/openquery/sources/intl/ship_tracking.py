"""ShipInfo — Vessel Position Tracking source.

Queries shipinfo.net for current vessel positions worldwide.
Parses vessel data from embedded JS using regex.
No browser or CAPTCHA required — direct HTTP.

Source: https://shipinfo.net/
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.ship_tracking import ShipTrackingResult, Vessel, VesselPosition
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SHIPINFO_URL = "https://shipinfo.net/vessels_map_75"
SHIPINFO_PAGE_URL = "https://shipinfo.net/"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


@register
class ShipTrackingSource(BaseSource):
    """Track vessel positions globally via shipinfo.net."""

    def __init__(self, timeout: float = 20.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.ship_tracking",
            display_name="ShipInfo \u2014 Vessel Position Tracking",
            description="Global vessel position tracking via shipinfo.net",
            country="INTL",
            url=SHIPINFO_PAGE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        vessel_name = input.extra.get("vessel_name", "").strip()
        imo = input.extra.get("imo", "").strip()
        mmsi = input.extra.get("mmsi", "").strip()

        # Also accept document_number as a fallback search term
        doc_number = input.document_number.strip()

        if not vessel_name and not imo and not mmsi and not doc_number:
            raise SourceError(
                "intl.ship_tracking",
                "Provide a search filter: extra.vessel_name, extra.imo, extra.mmsi, "
                "or document_number",
            )

        # Determine the display query string
        query_display = vessel_name or imo or mmsi or doc_number

        return self._search(
            vessel_name=vessel_name,
            imo=imo,
            mmsi=mmsi,
            fallback=doc_number,
            query_display=query_display,
        )

    def _search(
        self,
        vessel_name: str,
        imo: str,
        mmsi: str,
        fallback: str,
        query_display: str,
    ) -> ShipTrackingResult:
        try:
            with httpx.Client(timeout=self._timeout, verify=True) as client:
                resp = client.get(
                    SHIPINFO_URL,
                    headers={"User-Agent": USER_AGENT},
                )
                resp.raise_for_status()
                text = resp.text

            # Parse vessel data from JS response
            pattern = re.findall(
                r'"name"\s*:\s*"([^"]+)".*?"lat"\s*:\s*([\d.-]+).*?"lon"\s*:\s*([\d.-]+).*?'
                r'"speed"\s*:\s*([\d.-]+).*?"course"\s*:\s*([\d.-]+).*?'
                r'"imo"\s*:\s*"?(\d+)"?.*?"mmsi"\s*:\s*"?(\d+)"?',
                text,
                re.DOTALL,
            )

            if not pattern:
                logger.warning(
                    "No vessel data found in shipinfo.net response (length=%d)", len(text)
                )

            vessels: list[Vessel] = []

            for name, lat, lon, speed, course, v_imo, v_mmsi in pattern:
                # Apply filters
                if not self._matches(name, v_imo, v_mmsi, vessel_name, imo, mmsi, fallback):
                    continue

                tracking_url = f"https://www.marinetraffic.com/en/ais/details/ships/imo:{v_imo}"

                vessels.append(
                    Vessel(
                        name=name,
                        imo=v_imo,
                        mmsi=v_mmsi,
                        position=VesselPosition(
                            latitude=float(lat),
                            longitude=float(lon),
                            speed_knots=float(speed),
                            course=float(course),
                        ),
                        tracking_url=tracking_url,
                    )
                )

            return ShipTrackingResult(
                queried_at=datetime.now(),
                query=query_display,
                total=len(vessels),
                vessels=vessels,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "intl.ship_tracking",
                f"ShipInfo returned HTTP {e.response.status_code}",
            ) from e
        except httpx.RequestError as e:
            raise SourceError("intl.ship_tracking", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("intl.ship_tracking", f"Ship tracking search failed: {e}") from e

    @staticmethod
    def _matches(
        name: str,
        v_imo: str,
        v_mmsi: str,
        filter_name: str,
        filter_imo: str,
        filter_mmsi: str,
        fallback: str,
    ) -> bool:
        """Check if a vessel matches the provided search filters."""
        # If specific filters are set, match against them
        if filter_imo and filter_imo == v_imo:
            return True
        if filter_mmsi and filter_mmsi == v_mmsi:
            return True
        if filter_name and filter_name.lower() in name.lower():
            return True

        # If no specific filter matched but we have a fallback, try it as name search
        if not filter_name and not filter_imo and not filter_mmsi and fallback:
            return fallback.lower() in name.lower()

        # If specific filters were set but none matched
        if filter_imo or filter_mmsi or filter_name:
            return False

        return False
