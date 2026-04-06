"""BIS statistics source — Bank for International Settlements data.

Queries the BIS SDMX REST API v2 for financial statistics.
Free REST API, no auth, no CAPTCHA. Rate limit: 10 req/min.

API: https://data.bis.org/api/v2/
Docs: https://www.bis.org/statistics/sdmxfaq.htm
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.intl.bis import BisDataPoint, BisResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_BASE_URL = "https://data.bis.org/api/v2/data/{dataset}/{dimensions}"


@register
class BisSource(BaseSource):
    """Query BIS financial statistics via the SDMX REST API."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="intl.bis",
            display_name="BIS — Financial Statistics (Bank for International Settlements)",
            description=(
                "BIS SDMX REST API for financial and banking statistics "
                "(credit, debt, FX reserves, etc.)"
            ),
            country="INTL",
            url="https://data.bis.org/",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        dataset = input.extra.get("dataset", input.document_number).strip().upper()
        dimensions = input.extra.get("dimensions", "").strip()

        if not dataset:
            raise SourceError(
                "intl.bis",
                "Provide a dataset code (extra.dataset or document_number), e.g. WS_CPMI_CT2",
            )
        if not dimensions:
            raise SourceError(
                "intl.bis",
                "Provide dimension filters (extra.dimensions), e.g. 5A.5J.USD.A",
            )

        return self._fetch(dataset, dimensions)

    def _fetch(self, dataset: str, dimensions: str) -> BisResult:
        url = API_BASE_URL.format(dataset=dataset, dimensions=dimensions)
        params: dict[str, str] = {"format": "jsondata"}

        try:
            logger.info("Querying BIS: dataset=%s dimensions=%s", dataset, dimensions)

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OpenQuery/0.9.0)",
                "Accept": "application/json",
            }
            with httpx.Client(timeout=self._timeout, headers=headers) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

            data_points: list[BisDataPoint] = []
            details = ""

            # SDMX-JSON v2 structure
            structure = data.get("structure", {})
            dimensions_struct = structure.get("dimensions", {}).get("observation", [])
            time_labels: list[str] = []
            for dim in dimensions_struct:
                if dim.get("id") == "TIME_PERIOD":
                    time_labels = [v.get("id", "") for v in dim.get("values", [])]
                    break

            name = structure.get("name", "") or structure.get("description", "")
            if name:
                details = str(name)

            datasets = data.get("dataSets", [])
            if datasets:
                series_map = datasets[0].get("series", {})
                for _series_key, series_val in series_map.items():
                    observations = series_val.get("observations", {})
                    for idx_str, obs_vals in sorted(
                        observations.items(), key=lambda x: int(x[0])
                    ):
                        idx = int(idx_str)
                        period = time_labels[idx] if idx < len(time_labels) else idx_str
                        raw_val = obs_vals[0] if obs_vals else None
                        value_str = str(raw_val) if raw_val is not None else ""
                        data_points.append(BisDataPoint(period=period, value=value_str))

            return BisResult(
                queried_at=datetime.now(),
                dataset=dataset,
                dimensions=dimensions,
                data_points=data_points,
                details=details,
            )

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "intl.bis", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("intl.bis", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("intl.bis", f"Query failed: {e}") from e
