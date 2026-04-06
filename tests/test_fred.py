"""Tests for us.fred — Federal Reserve FRED economic time series.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestFredResult — model tests
# ===========================================================================


class TestFredResult:
    def test_defaults(self):
        from openquery.models.us.fred import FredResult

        r = FredResult()
        assert r.series_id == ""
        assert r.series_name == ""
        assert r.data_points == []
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.us.fred import FredDataPoint, FredResult

        r = FredResult(
            series_id="GDP",
            series_name="Gross Domestic Product",
            data_points=[
                FredDataPoint(date="2022-01-01", value="25015.8"),
                FredDataPoint(date="2022-04-01", value="24882.9"),
            ],
        )
        dumped = r.model_dump_json()
        restored = FredResult.model_validate_json(dumped)
        assert restored.series_id == "GDP"
        assert restored.series_name == "Gross Domestic Product"
        assert len(restored.data_points) == 2

    def test_audit_excluded_from_json(self):
        from openquery.models.us.fred import FredResult

        r = FredResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_data_point_defaults(self):
        from openquery.models.us.fred import FredDataPoint

        dp = FredDataPoint()
        assert dp.date == ""
        assert dp.value == ""


# ===========================================================================
# TestFredSourceMeta
# ===========================================================================


class TestFredSourceMeta:
    def test_meta_name(self):
        from openquery.sources.us.fred import FredSource

        meta = FredSource().meta()
        assert meta.name == "us.fred"

    def test_meta_country(self):
        from openquery.sources.us.fred import FredSource

        meta = FredSource().meta()
        assert meta.country == "US"

    def test_meta_no_captcha(self):
        from openquery.sources.us.fred import FredSource

        meta = FredSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.us.fred import FredSource

        meta = FredSource().meta()
        assert meta.rate_limit_rpm == 20

    def test_meta_supports_custom(self):
        from openquery.sources.us.fred import FredSource

        meta = FredSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestFredParseResult
# ===========================================================================

MOCK_FRED_SERIES_RESPONSE = {
    "seriess": [
        {
            "id": "GDP",
            "title": "Gross Domestic Product",
            "frequency": "Quarterly",
            "units": "Billions of Dollars",
        }
    ]
}

MOCK_FRED_OBS_RESPONSE = {
    "observations": [
        {"date": "2022-04-01", "value": "24882.9"},
        {"date": "2022-01-01", "value": "25015.8"},
    ]
}


class TestFredParseResult:
    def _make_input(self, series_id: str = "GDP") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"series_id": series_id},
        )

    def _make_mock_client(self, series_resp, obs_resp) -> MagicMock:
        mock_series = MagicMock()
        mock_series.json.return_value = series_resp
        mock_series.raise_for_status = MagicMock()

        mock_obs = MagicMock()
        mock_obs.json.return_value = obs_resp
        mock_obs.raise_for_status = MagicMock()

        mock_client = MagicMock()
        call_count = [0]

        def side_effect(url, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_series
            return mock_obs

        mock_client.get.side_effect = side_effect
        return mock_client

    def test_successful_query(self):
        from openquery.sources.us.fred import FredSource

        mock_client = self._make_mock_client(MOCK_FRED_SERIES_RESPONSE, MOCK_FRED_OBS_RESPONSE)

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = FredSource()
            result = source.query(self._make_input())

        assert result.series_id == "GDP"
        assert result.series_name == "Gross Domestic Product"
        assert len(result.data_points) == 2
        # reversed order: sorted chronologically (oldest first)
        assert result.data_points[0].date == "2022-01-01"
        assert result.data_points[0].value == "25015.8"

    def test_missing_series_id_raises(self):
        from openquery.sources.us.fred import FredSource

        source = FredSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={},
        )
        with pytest.raises(SourceError, match="series ID"):
            source.query(inp)

    def test_series_id_uppercased(self):
        from openquery.sources.us.fred import FredSource

        mock_client = self._make_mock_client(MOCK_FRED_SERIES_RESPONSE, MOCK_FRED_OBS_RESPONSE)

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = FredSource()
            inp = QueryInput(
                document_number="gdp",
                document_type=DocumentType.CUSTOM,
                extra={},
            )
            result = source.query(inp)

        assert result.series_id == "GDP"

    def test_missing_value_replaced_with_empty(self):
        from openquery.sources.us.fred import FredSource

        obs_with_dot = {"observations": [{"date": "2022-01-01", "value": "."}]}
        mock_client = self._make_mock_client(MOCK_FRED_SERIES_RESPONSE, obs_with_dot)

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = FredSource()
            result = source.query(self._make_input())

        assert result.data_points[0].value == ""

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.us.fred import FredSource

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = FredSource()
            with pytest.raises(SourceError, match="us.fred"):
                source.query(self._make_input())
