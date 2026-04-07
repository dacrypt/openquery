"""CarQuery vehicle specs source — global vehicle trim data.

Queries CarQuery API for vehicle trim/engine/body specs.
Free REST API, no auth required. Returns JSONP — strip callback wrapper.

API: https://www.carqueryapi.com/api/0.3/?cmd=getTrims
"""

from __future__ import annotations

import json
import logging
import re

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.carquery import UsCarQueryResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_URL = "https://www.carqueryapi.com/api/0.3/"

# JSONP callback pattern: callback({...}) or callback([...])
_JSONP_RE = re.compile(r"^\w+\((.+)\);?\s*$", re.DOTALL)


def _strip_jsonp(text: str) -> str:
    """Strip JSONP callback wrapper and return raw JSON string."""
    m = _JSONP_RE.match(text.strip())
    if m:
        return m.group(1)
    return text


@register
class CarQuerySource(BaseSource):
    """Query CarQuery API for vehicle trim specifications."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.carquery",
            display_name="CarQuery — Vehicle Trim Specifications",
            description="Global vehicle trim specs (engine, fuel, body, doors, seats) from CarQuery API",  # noqa: E501
            country="US",
            url="https://www.carqueryapi.com/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        make = input.extra.get("make", "").strip()
        model = input.extra.get("model", "").strip()
        year = input.extra.get("year", "").strip()

        if not make:
            raise SourceError("us.carquery", "Provide extra['make'] (vehicle manufacturer)")

        params: dict[str, str] = {"cmd": "getTrims"}
        if make:
            params["make"] = make
        if model:
            params["model"] = model
        if year:
            params["year"] = year

        logger.info("Querying CarQuery: make=%s model=%s year=%s", make, model, year)

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json, text/javascript, */*",
                "Referer": "https://www.carqueryapi.com/",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                raw = resp.text

            json_str = _strip_jsonp(raw)
            data = json.loads(json_str)

            trims_raw = data.get("Trims", [])
            trims = []
            for t in trims_raw:
                trims.append({
                    "make": t.get("make_display", make),
                    "model": t.get("model_name", model),
                    "year": t.get("model_year", year),
                    "trim": t.get("model_trim", ""),
                    "body_style": t.get("model_body", ""),
                    "engine": t.get("model_engine_cc", ""),
                    "fuel_type": t.get("model_engine_fuel", ""),
                    "doors": t.get("model_doors", ""),
                    "seats": t.get("model_seats", ""),
                })

            first = trims[0] if trims else {}
            return UsCarQueryResult(
                make=first.get("make", make),
                model=first.get("model", model),
                year=first.get("year", year),
                trim=first.get("trim", ""),
                body_style=first.get("body_style", ""),
                engine=first.get("engine", ""),
                fuel_type=first.get("fuel_type", ""),
                doors=first.get("doors", ""),
                seats=first.get("seats", ""),
                details=f"{len(trims)} trim(s) found for {make} {model} {year}".strip(),
                trims=trims[:20],
            )

        except SourceError:
            raise
        except httpx.HTTPStatusError as e:
            raise SourceError("us.carquery", f"API returned HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SourceError("us.carquery", f"Request failed: {e}") from e
        except json.JSONDecodeError as e:
            raise SourceError("us.carquery", f"Failed to parse response: {e}") from e
        except Exception as e:
            raise SourceError("us.carquery", f"Query failed: {e}") from e
